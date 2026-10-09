// CPU-only fault injection against the real plugin initialization/cleanup code.
#include <algorithm>
#include <chrono>
#include <iostream>
#include <set>
#include <stdexcept>
#include <vector>
#include "RGLServerPluginInstance.hh"

namespace {
int calls = 0, failAt = 0;
uintptr_t serial = 0;
std::set<rgl_node_t> live;
std::vector<std::pair<rgl_node_t, rgl_node_t>> edges;
bool fail() { return ++calls == failAt; }
rgl_status_t create(rgl_node_t* node) {
    if (fail()) return RGL_INVALID_ARGUMENT;
    *node = reinterpret_cast<rgl_node_t>(++serial);
    live.insert(*node);
    return RGL_SUCCESS;
}
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
}

extern "C" {
// The CPU test does not link the real GPU library. Unexpected scan calls fail.
rgl_status_t rgl_get_version_info(int32_t* major, int32_t* minor, int32_t* patch) {
    *major = RGL_VERSION_MAJOR; *minor = RGL_VERSION_MINOR; *patch = RGL_VERSION_PATCH;
    return RGL_SUCCESS;
}
rgl_status_t rgl_graph_run(rgl_node_t) { throw std::runtime_error("unexpected scan in initialization test"); }
rgl_status_t rgl_graph_get_result_size(rgl_node_t, rgl_field_t, int32_t*, int32_t*) {
    throw std::runtime_error("unexpected result query");
}
rgl_status_t rgl_graph_get_result_data(rgl_node_t, rgl_field_t, void*) {
    throw std::runtime_error("unexpected result query");
}
void __wrap_rgl_get_last_error_string(const char** text) { *text = "injected initialization failure"; }
rgl_status_t __wrap_rgl_node_rays_from_mat3x4f(rgl_node_t* n, const rgl_mat3x4f*, int32_t) { return create(n); }
rgl_status_t __wrap_rgl_node_rays_set_range(rgl_node_t* n, const rgl_vec2f*, int32_t) { return create(n); }
rgl_status_t __wrap_rgl_node_rays_transform(rgl_node_t* n, const rgl_mat3x4f*) { return create(n); }
rgl_status_t __wrap_rgl_node_points_transform(rgl_node_t* n, const rgl_mat3x4f*) { return create(n); }
rgl_status_t __wrap_rgl_node_raytrace(rgl_node_t* n, rgl_scene_t) { return create(n); }
rgl_status_t __wrap_rgl_node_points_compact_by_field(rgl_node_t* n, rgl_field_t) { return create(n); }
rgl_status_t __wrap_rgl_node_points_yield(rgl_node_t* n, const rgl_field_t*, int32_t) { return create(n); }
rgl_status_t __wrap_rgl_node_points_format(rgl_node_t* n, const rgl_field_t*, int32_t) { return create(n); }
rgl_status_t __wrap_rgl_graph_node_add_child(rgl_node_t p, rgl_node_t c) {
    if (fail()) return RGL_INVALID_ARGUMENT;
    require(live.contains(p) && live.contains(c), "connecting dead node");
    edges.emplace_back(p,c);
    return RGL_SUCCESS;
}
rgl_status_t __wrap_rgl_graph_node_set_priority(rgl_node_t, int32_t) {
    return fail() ? RGL_INVALID_ARGUMENT : RGL_SUCCESS;
}
rgl_status_t __wrap_rgl_graph_node_remove_child(rgl_node_t p, rgl_node_t c) {
    std::erase(edges, std::make_pair(p,c));
    return RGL_SUCCESS;
}
rgl_status_t __wrap_rgl_graph_destroy(rgl_node_t root) {
    require(live.contains(root), "double destroy or invalid node");
    std::set<rgl_node_t> component{root};
    bool changed = true;
    while (changed) {
        changed = false;
        for (auto [p,c] : edges) {
            if (component.contains(p)) changed |= component.insert(c).second;
            if (component.contains(c)) changed |= component.insert(p).second;
        }
    }
    for (auto n : component) require(live.erase(n) == 1, "graph has dead node");
    std::erase_if(edges, [&](auto edge) { return component.contains(edge.first); });
    return RGL_SUCCESS;
}
}

namespace rgl {
class RGLInstanceTest {
public:
    static int run(bool laser, int failure) {
        calls = 0; failAt = failure;
        require(live.empty(), "leaked graph from previous case");
        RGLServerPluginInstance plugin;
        plugin.lidarPattern.resize(4);
        plugin.lidarPatternSampleSize = 2;
        plugin.topicName = laser ? "/fault_test/scan" : "/fault_test/points";
        plugin.frameId = "test_lidar";
        plugin.publishLaserScan = laser;
        plugin.raytraceIntervalTime = std::chrono::milliseconds(100);
        gz::sim::EntityComponentManager ecm;
        plugin.CreateLidar(42, ecm);
        const auto count = calls;
        require(plugin.isLidarInitialized == (failure == 0), "wrong initialization status");
        if (failure) {
            require(live.empty(), "partial initialization leaked nodes");
            require(!plugin.ShouldRayTrace(std::chrono::seconds(1), false), "failed sensor still scans");
        } else {
            // Also exercise detached / reattached alternating-pattern ownership.
            plugin.UpdateAlternatingLidarPattern();
            plugin.UpdateAlternatingLidarPattern();
            plugin.pendingDestroy = true;
            plugin.PreUpdate(gz::sim::UpdateInfo{}, ecm);
            require(!plugin.isLidarInitialized && live.empty(), "deferred cleanup failed");
        }
        plugin.DestroyLidar();
        plugin.DestroyLidar();
        require(live.empty() && edges.empty(), "cleanup leaked a disconnected component");
        return count;
    }
};
}

int main() {
    try {
        int cases = 0;
        for (bool laser : {false,true}) {
            int steps = rgl::RGLInstanceTest::run(laser, 0);
            for (int step=1; step<=steps; ++step) {
                rgl::RGLInstanceTest::run(laser, step);
                ++cases;
            }
        }
        std::cout << cases << " initialization failure points verified; no GPU required.\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << e.what() << "\n";
        return 1;
    }
}

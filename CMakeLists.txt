cmake_minimum_required(VERSION 3.22)
project(livox_lidar_simulation_gz VERSION 0.1.0)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(gz_cmake_vendor REQUIRED)
find_package(gz_plugin_vendor REQUIRED)
find_package(gz_sim_vendor REQUIRED)
find_package(gz-cmake3 REQUIRED)
gz_find_package(gz-plugin2 REQUIRED COMPONENTS register)
gz_find_package(gz-sim8 REQUIRED)
include(cmake/RGLDependencies.cmake)

set(upstream "${CMAKE_CURRENT_SOURCE_DIR}/third_party/rgl_gazebo/RGLServerPlugin")
add_library(RGLServerPluginManager SHARED
  ${upstream}/src/RGLServerPluginManager.cc ${upstream}/src/Mesh.cc
  ${upstream}/src/Utils.cc ${upstream}/src/Scene.cc)
add_library(RGLServerPluginInstance SHARED
  ${upstream}/src/RGLServerPluginInstance.cc ${upstream}/src/Lidar.cc
  ${upstream}/src/Utils.cc ${upstream}/src/LidarPatternLoader.cc)
foreach(target RGLServerPluginManager RGLServerPluginInstance)
  target_compile_features(${target} PRIVATE cxx_std_20)
  target_include_directories(${target} PRIVATE "${upstream}/include")
  target_link_libraries(${target} PRIVATE
    gz-plugin2::gz-plugin2 gz-sim8::gz-sim8 RobotecGPULidar)
  set_target_properties(${target} PROPERTIES INSTALL_RPATH "$ORIGIN")
endforeach()
install(TARGETS RGLServerPluginManager RGLServerPluginInstance
  LIBRARY DESTINATION lib/${PROJECT_NAME}/rgl)
install(IMPORTED_RUNTIME_ARTIFACTS RobotecGPULidar
  LIBRARY DESTINATION lib/${PROJECT_NAME}/rgl)
install(FILES "${LIVOX_RGL_CACHE}/patterns/LivoxMid360.mat3x4f"
  "${LIVOX_RGL_CACHE}/patterns/LivoxAvia.mat3x4f"
  DESTINATION share/${PROJECT_NAME}/patterns)
ament_python_install_package(${PROJECT_NAME})
install(DIRECTORY launch config urdf worlds rviz
  DESTINATION share/${PROJECT_NAME})
foreach(model mid360 avia)
  install(FILES meshes/${model}/${model}.dae meshes/${model}/${model}.glb
    meshes/${model}/geometry_report.json meshes/${model}/NOTICE.md
    DESTINATION share/${PROJECT_NAME}/meshes/${model})
endforeach()
install(FILES README.md README.en.md LICENSE NOTICE THIRD_PARTY_NOTICES.md CONTRIBUTING.md
  DESTINATION share/${PROJECT_NAME})
install(FILES third_party/rgl_gazebo/LICENSE third_party/rgl_gazebo/UPSTREAM.md
  DESTINATION share/${PROJECT_NAME}/third_party/rgl_gazebo)
install(FILES third_party/livox_scan/LICENSE DESTINATION share/${PROJECT_NAME}/third_party/livox_scan)
install(FILES dependencies/lock.json DESTINATION share/${PROJECT_NAME}/dependencies)
install(FILES docs/INTEGRATION.md docs/SUPPORT.md docs/TROUBLESHOOTING.md
  DESTINATION share/${PROJECT_NAME}/docs)
ament_environment_hooks(hooks/livox_gz.dsv.in)
if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(unit_tests test TIMEOUT 60)
endif()
ament_package()

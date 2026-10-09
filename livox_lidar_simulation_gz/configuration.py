"""Small shared contract used by launch files and tests."""

import math
import json
from pathlib import Path
import re

import yaml


def load_model(share, model):
    if model not in ('mid360', 'avia'):
        raise ValueError(f'Unsupported model: {model}; available: mid360, avia')
    config = yaml.safe_load((Path(share) / 'config/models' / f'{model}.yaml').read_text())
    if not isinstance(config, dict) or config.get('model') != model or type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        raise ValueError('Model/config mismatch')
    layout = json.loads((Path(share) / 'dependencies/lock.json').read_text())['scan_presets'][model]
    if set(config) & set(layout):
        raise ValueError('Scan layout is read-only; edit dependencies/lock.json with the matching preset')
    for key in ('pattern_groups', 'rays_per_frame'):
        if type(layout[key]) is not int or layout[key] <= 0:
            raise ValueError(f'{key} must be a positive integer')
    if Path(layout['pattern_file']).name != layout['pattern_file']:
        raise ValueError('Pattern filename must not contain a path')
    config.update(layout)
    for key in ('lidar_rate', 'imu_rate', 'mass', 'size_x', 'size_y', 'size_z',
                'collision_body_height', 'range_max'):
        number(config.get(key), key, positive=True)
    low, high = number(config.get('range_min'), 'range_min'), config['range_max']
    if not 0 <= low < high:
        raise ValueError('Invalid range')
    if config['mass'] <= 0.000002 or config['lidar_rate'] > 1e6 or config['imu_rate'] > 1e6:
        raise ValueError('Mass or update rate exceeds supported limits')
    for key in ('measurement_xyz', 'imu_xyz', 'imu_from_lidar_xyz'):
        vector3(config[key], key)
        for value in config[key]:
            number(value, key)
    if not (abs(config['measurement_xyz'][0]) <= config['size_x']/2
            and abs(config['measurement_xyz'][1]) <= config['size_y']/2
            and 0 < config['measurement_xyz'][2] <= config['size_z']):
        raise ValueError('Invalid measurement origin')
    expected = [a-b for a,b in zip(config['imu_xyz'], config['measurement_xyz'])]
    if not all(math.isclose(a, b, abs_tol=1e-8) for a, b in zip(expected, config['imu_from_lidar_xyz'])):
        raise ValueError('IMU offsets disagree with measurement origin')
    if type(config.get('connector_collision')) is not bool:
        raise ValueError('connector_collision must be boolean')
    if config['connector_collision']:
        connector = config.get('connector', {})
        vector3(connector.get('xyz'), 'connector.xyz')
        vector3(connector.get('rpy'), 'connector.rpy')
        if connector.get('shape') == 'cylinder':
            for key in ('radius', 'length'):
                number(connector.get(key), 'connector.' + key, positive=True)
        elif connector.get('shape') == 'box':
            if not all(float(v) > 0 for v in vector3(connector.get('size'), 'connector.size').split()):
                raise ValueError('connector.size must be positive')
        else:
            raise ValueError('Unsupported connector shape')
    return config


def number(value, field, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or (positive and value <= 0):
        raise ValueError(f'{field} must be a finite number' + (' greater than zero' if positive else ''))
    return value


def sensor_topics(namespace, name, points_topic='', imu_topic=''):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('Sensor name must start with a letter and use letters/digits/underscores')
    namespace = namespace.strip('/')
    if namespace and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*', namespace):
        raise ValueError('Invalid namespace')
    root = '/' + '/'.join(part for part in (namespace, name) if part)
    topics = (points_topic or root + '/points', imu_topic or root + '/imu')
    for topic in topics:
        validate_topic(topic)
    if topics[0] == topics[1]:
        raise ValueError('Point cloud and IMU topics must be different')
    return topics


def validate_topic(topic):
    if not isinstance(topic, str) or not re.fullmatch(r'(/[A-Za-z_][A-Za-z0-9_]*)+', topic):
        raise ValueError('Topics must be absolute ROS-compatible paths')
    return topic


def boolean(value):
    normalized = str(value).lower()
    if normalized not in ('true', 'false'):
        raise ValueError(f'Expected true or false, got {value}')
    return normalized == 'true'


def vector3(value, field):
    """Normalize a YAML vector or launch argument without permitting NaN/Inf."""
    values = value.split() if isinstance(value, str) else value
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError(f'{field} requires three numbers')
    if any(isinstance(item, bool) for item in values):
        raise ValueError(f'{field} cannot contain booleans')
    try:
        numbers = [float(item) for item in values]
    except (TypeError, ValueError) as error:
        raise ValueError(f'{field} requires three numbers') from error
    if not all(math.isfinite(item) for item in numbers):
        raise ValueError(f'{field} must be finite')
    return ' '.join(str(item) for item in numbers)


def load_sensors(share, sensors_file='', defaults=None):
    """One validated instance contract shared by the single and multi demo."""
    if sensors_file:
        data = yaml.safe_load(Path(sensors_file).read_text())
        if not isinstance(data, dict) or set(data) != {'sensors'}:
            raise ValueError('Instance file must contain only a sensors list')
        rows = data['sensors']
    else:
        rows = [defaults or {}]
    if not isinstance(rows, list) or not rows:
        raise ValueError('sensors must be a nonempty list')
    baseline = dict(model='mid360', name='mid360', namespace='livox',
                    xyz='0 0 1', rpy='0 0 0', visual_mesh='', mesh_rpy='0 0 0',
                    points_topic='', imu_topic='')
    names, topics, result = set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) - set(baseline):
            raise ValueError('Invalid sensor instance or unknown keys')
        item = {**baseline, **row}
        for field in ('model', 'name', 'namespace', 'visual_mesh', 'points_topic', 'imu_topic'):
            if not isinstance(item[field], str):
                raise ValueError(f'{field} must be a string')
        load_model(share, item['model'])
        if item['model'] == 'avia' and item['visual_mesh'] == 'primitive':
            raise ValueError('Avia primitive appearance has been removed; use the detailed mesh')
        points, imu = sensor_topics(item['namespace'], item['name'], item['points_topic'], item['imu_topic'])
        if item['name'] in names:
            raise ValueError(f'Duplicate sensor name / TF prefix: {item["name"]}')
        if points in topics or imu in topics:
            raise ValueError('Duplicate sensor topics')
        names.add(item['name'])
        topics.update((points, imu))
        for field in ('xyz', 'rpy', 'mesh_rpy'):
            item[field] = vector3(item[field], field)
        item.update(points_topic=points, imu_topic=imu)
        result.append(item)
    return result

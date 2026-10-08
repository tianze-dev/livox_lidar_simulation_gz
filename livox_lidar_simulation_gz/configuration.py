"""Small shared contract used by launch files and tests."""

import math
from pathlib import Path
import re

import yaml


def load_model(share, model):
    if model != 'mid360':
        raise ValueError(f'Unsupported model: {model}; only mid360 is implemented')
    config = yaml.safe_load((Path(share) / 'config/models' / f'{model}.yaml').read_text())
    if config['model'] != model:
        raise ValueError('Model/config mismatch')
    for key in ('lidar_rate', 'imu_rate', 'mass', 'size_x', 'size_y', 'size_z'):
        value = float(config[key])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{key} must be finite and positive')
    low, high = float(config['range_min']), float(config['range_max'])
    if not (math.isfinite(low) and math.isfinite(high) and 0 <= low < high):
        raise ValueError('Invalid range')
    return config


def sensor_topics(namespace, name):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name):
        raise ValueError('Sensor name must start with a letter and use letters/digits/underscores')
    namespace = namespace.strip('/')
    if namespace and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(/[A-Za-z_][A-Za-z0-9_]*)*', namespace):
        raise ValueError('Invalid namespace')
    root = '/' + '/'.join(part for part in (namespace, name) if part)
    return root + '/points', root + '/imu'


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
                    xyz='0 0 1', rpy='0 0 0', visual_mesh='', mesh_rpy='0 0 0')
    names, topics, result = set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) - set(baseline):
            raise ValueError('Invalid sensor instance or unknown keys')
        item = {**baseline, **row}
        for field in ('model', 'name', 'namespace', 'visual_mesh'):
            if not isinstance(item[field], str):
                raise ValueError(f'{field} must be a string')
        load_model(share, item['model'])
        points, imu = sensor_topics(item['namespace'], item['name'])
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

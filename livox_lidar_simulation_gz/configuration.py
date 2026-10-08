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

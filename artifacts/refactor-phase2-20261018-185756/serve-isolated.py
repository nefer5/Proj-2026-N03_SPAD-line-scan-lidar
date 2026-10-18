"""UI verification with a domain-layout copy, never the real defaults file."""
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from spad_lidar import configuration, default_store
OUT = Path(__file__).resolve().parent
config = OUT / 'browser-config'
if not config.exists():
    shutil.copytree(OUT / 'candidate-config', config)
configuration.CONFIG_DIR = config
default_store.BACKUP_DIR = OUT / 'browser-backups'
from spad_lidar.api import app
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=18766)

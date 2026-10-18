"""Explicit default persistence, separate from drafts and immutable jobs."""
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
import yaml
from .. import default_store

router = APIRouter()


class DefaultWrite(BaseModel):
    model_config = ConfigDict(extra='forbid')
    config: dict
    revision: str | None = Field(default=None, pattern=r'^[0-9a-f]{64}$')


@router.post('/api/defaults/{kind}/{action}')
def defaults(kind: str, action: str, body: DefaultWrite, request: Request):
    origin = request.headers.get('origin')
    if request.headers.get('sec-fetch-site') == 'cross-site' or (origin and
            (urlsplit(origin).scheme, urlsplit(origin).netloc) != (request.url.scheme, request.url.netloc)):
        raise HTTPException(403, '请从本项目网页保存默认配置。')
    try:
        if action == 'preview':
            return default_store.preview(kind, body.config)
        if action == 'save' and body.revision is not None:
            return default_store.save(kind, body.config, body.revision)
        raise ValueError('保存需要预览版本；操作仅支持 preview/save')
    except default_store.DefaultConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, KeyError, TypeError, OverflowError, yaml.YAMLError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(503, f'默认配置未能保存，请检查目录写入权限：{exc}') from exc

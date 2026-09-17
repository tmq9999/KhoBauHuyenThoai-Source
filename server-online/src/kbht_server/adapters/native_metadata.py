"""Pinned local build metadata, never a historical endpoint proxy or file server."""
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, Response

MAX_MANIFEST = 2 * 1024 * 1024


def load_manifest(path, expected_sha256):
    path = Path(path).absolute()
    if not isinstance(expected_sha256, str) or re.fullmatch('[0-9a-f]{64}', expected_sha256) is None:
        raise ValueError('Explicit manifest SHA256 required')
    for part in (path, *path.parents):
        info = part.lstat()
        if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('Manifest path must not be linked')
    with path.open('rb') as source:
        raw = source.read(MAX_MANIFEST + 1)
    if len(raw) > MAX_MANIFEST or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('Manifest size or hash mismatch')
    data = json.loads(raw)
    version = data.get('version') if isinstance(data, dict) else None
    if not isinstance(version, str) or re.fullmatch(r'[A-Za-z0-9._-]{1,100}', version) is None:
        raise ValueError('Invalid manifest version')
    origin = 'http://127.0.0.1:20001'
    expected = {'host': '127.0.0.1:20001', 'packageUrl': origin+'/update/'+version,
                'remoteVersionUrl': origin+'/update/version.manifest',
                'remoteManifestUrl': origin+'/update/project.manifest'}
    if any(data.get(key) != value for key, value in expected.items()):
        raise ValueError('Manifest endpoints must match local native metadata')
    assets = data.get('assets')
    if not isinstance(assets, dict) or not assets:
        raise ValueError('Manifest assets missing')
    for name, entry in assets.items():
        if (not isinstance(name, str) or '\\' in name or ':' in name or
                PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts or
                not isinstance(entry, dict) or not isinstance(entry.get('md5'), str) or
                re.fullmatch('[0-9a-fA-F]{32}', entry['md5']) is None):
            raise ValueError('Invalid manifest asset')
    return version, raw


def create_native_metadata_app(path, expected_sha256):
    version, raw = load_manifest(path, expected_sha256)
    bodies = {
        '/client_config.json': b'{"runScriptInfo":{"script":""},"inReviewPackageInfos":[]}',
        '/notice.json': b'[]',
        '/update/version.manifest': json.dumps({'version': version}, separators=(',', ':')).encode(),
        '/update/project.manifest': raw,
    }
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.api_route('/{path:path}', methods=['GET', 'HEAD'])
    async def metadata(request: Request, path: str):
        body = bodies.get('/'+path)
        if request.url.query or body is None:
            return JSONResponse({'error': 'not found'}, status_code=404, headers={'Cache-Control': 'no-store'})
        headers = {'Cache-Control': 'no-store', 'Content-Length': str(len(body))}
        return Response(body if request.method == 'GET' else b'', media_type='application/json', headers=headers)

    return app

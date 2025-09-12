import os
from config import Config
from typing import List

try:
    import yadisk
except Exception:
    yadisk = None


class CloudStorage:
    def __init__(self):
        self.client = None
        if yadisk and Config.YANDEX_TOKEN:
            try:
                self.client = yadisk.YaDisk(token=Config.YANDEX_TOKEN)
            except Exception:
                self.client = None
        # WebDAV (Mail.ru Cloud)
        self.webdav = None
        try:
            from webdav3.client import Client as WebDavClient
            options = {
                'webdav_hostname': Config.WEBDAV_URL,
                'webdav_login': Config.WEBDAV_LOGIN,
                'webdav_password': Config.WEBDAV_PASSWORD,
                'disable_check': True,
            }
            self.webdav = WebDavClient(options)
        except Exception:
            self.webdav = None

    def create_student_folder(self, student_name, group_name):
        path = f'/Assignments/{group_name}/{student_name}'
        if not self.client:
            os.makedirs(os.path.join('uploads', group_name, student_name), exist_ok=True)
            return path
        try:
            if not self.client.exists(path):
                self.client.mkdir(path)
            return path
        except Exception as e:
            print(f"Error creating folder: {e}")
            return None

    def upload_assignment(self, file_path, student_name, group_name, assignment_title):
        folder = self.create_student_folder(student_name, group_name)
        if folder and self.client:
            cloud_path = f'{folder}/{assignment_title}'
            try:
                self.client.upload(file_path, cloud_path)
                return self.client.get_download_link(cloud_path)
            except Exception as e:
                print(f"Upload error: {e}")
                return None
        elif folder:
            # Local fallback
            dest_dir = os.path.join('uploads', group_name, student_name)
            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, assignment_title)
            try:
                with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    dst.write(src.read())
                return dest_path
            except Exception as e:
                print(f"Local upload error: {e}")
                return None

    def download_submission(self, cloud_path, local_path):
        if not self.client:
            try:
                with open(cloud_path, 'rb') as src, open(local_path, 'wb') as dst:
                    dst.write(src.read())
                return True
            except Exception as e:
                print(f"Local download error: {e}")
                return False
        try:
            self.client.download(cloud_path, local_path)
            return True
        except Exception as e:
            print(f"Download error: {e}")
            return False

    def list_submissions(self, student_name, group_name):
        if not self.client and not self.webdav:
            path = os.path.join('uploads', group_name, student_name)
            try:
                if os.path.exists(path):
                    return [type('Obj', (), {'name': f, 'path': os.path.join(path, f)}) for f in os.listdir(path)]
                return []
            except Exception as e:
                print(f"Local list error: {e}")
                return []
        # Try Yandex Disk first
        if self.client:
            path = f'/Assignments/{group_name}/{student_name}/submissions'
            try:
                if self.client.exists(path):
                    return list(self.client.listdir(path))
            except Exception as e:
                print(f"Yandex list error: {e}")
        # WebDAV (Mail.ru Cloud)
        if self.webdav:
            cloud_path = Config.WEBDAV_ROOT_PATH.rstrip('/') + f'/{group_name}/{student_name}'
            try:
                # webdavclient3 returns list of dicts with 'href'
                items = self.webdav.list(cloud_path)
                cleaned: List[object] = []
                for href in items:
                    name = href.rstrip('/').split('/')[-1]
                    cleaned.append(type('Obj', (), {'name': name, 'path': href}))
                return cleaned
            except Exception as e:
                print(f"WebDAV list error: {e}")
        return []

    def list_group_folders(self, group_name: str):
        """List folders for a path under cloud root (Mail.ru WebDAV or local fallback)."""
        # Local fallback
        if not self.webdav:
            root_local = os.path.join('uploads', group_name) if group_name else 'uploads'
            try:
                if os.path.exists(root_local):
                    return [{'name': f, 'path': os.path.join(root_local, f)} for f in os.listdir(root_local)]
            except Exception as e:
                print(f"Local group list error: {e}")
            return []
        # WebDAV
        base = (Config.WEBDAV_ROOT_PATH.rstrip('/') + ('/' + group_name if group_name else '/')).replace('//', '/')
        try:
            items = self.webdav.list(base)
            out = []
            for href in items:
                if href == base or href.rstrip('/') == base.rstrip('/'):
                    continue
                name = href.rstrip('/').split('/')[-1]
                is_dir = href.endswith('/')
                out.append({'name': name, 'path': href, 'type': 'dir' if is_dir else 'file'})
            return out
        except Exception as e:
            print(f"WebDAV group list error: {e}")
            return []

    def list_root_folders(self):
        """List folders in cloud root."""
        return self.list_group_folders('')

    def mkdir(self, rel_path: str):
        if self.webdav:
            p = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + rel_path.strip('/')).replace('//', '/')
            self.webdav.mkdir(p)
            return True
        os.makedirs(os.path.join('uploads', rel_path), exist_ok=True)
        return True

    def upload(self, rel_path: str, file_storage):
        # rel_path includes folders + filename
        if self.webdav:
            p = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + rel_path.strip('/')).replace('//', '/')
            # ensure parent directory exists
            parent = '/'.join(p.rstrip('/').split('/')[:-1]) or '/'
            try:
                self._ensure_dir(parent)
            except Exception as e:
                print('ensure_dir error', e)
            # save temp then upload
            tmp = os.path.join('uploads', '__tmp__')
            os.makedirs(tmp, exist_ok=True)
            tmp_file = os.path.join(tmp, file_storage.filename)
            file_storage.save(tmp_file)
            try:
                self.webdav.upload_sync(remote_path=p, local_path=tmp_file)
            finally:
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
            return True
        # local
        dest = os.path.join('uploads', rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        file_storage.save(dest)
        return True

    def download(self, rel_path: str, local_dest: str):
        if self.webdav:
            p = (Config.WEBDAV_ROOT_PATH.rstrip('/') + '/' + rel_path.strip('/')).replace('//', '/')
            self.webdav.download_sync(remote_path=p, local_path=local_dest)
            return True
        # local
        src = os.path.join('uploads', rel_path)
        os.makedirs(os.path.dirname(local_dest), exist_ok=True)
        with open(src, 'rb') as s, open(local_dest, 'wb') as d:
            d.write(s.read())
        return True

    def _ensure_dir(self, remote_path: str):
        """Recursively ensure remote directories exist for WebDAV."""
        if not self.webdav:
            return
        norm = remote_path.replace('//', '/')
        if norm in ('', '/'):
            return
        parts = norm.strip('/').split('/')
        path = ''
        for part in parts:
            path += '/' + part
            try:
                # list to check existence
                self.webdav.list(path)
            except Exception:
                try:
                    self.webdav.mkdir(path)
                except Exception:
                    pass
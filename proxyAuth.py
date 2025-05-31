import os
import zipfile


def create_proxy_extension(name: str, proxy: str, extension_dir) -> str:
    # Tách thông tin proxy
    PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS = proxy.split(":")

    # Nội dung của manifest.json
    manifest_json = f'''
    {{
      "name": "Chrome Proxy",
      "version": "1.0.0",
      "manifest_version": 3,
      "permissions": [
        "proxy",
        "storage",
        "webRequest",      
        "webRequestAuthProvider"
      ],
      "host_permissions": [
        "<all_urls>"
      ],
      "background": {{
        "service_worker": "background.js"
      }},
      "minimum_chrome_version": "108"
    }}
    '''

    # Nội dung của background.js
    background_js = f'''
    const config = {{
      mode: "fixed_servers",
      rules: {{
        singleProxy: {{
          scheme: "http",
          host: "{PROXY_HOST}",
          port: parseInt("{PROXY_PORT}")
        }},
        bypassList: ["localhost"]
      }}
    }};
    
    chrome.proxy.settings.set({{ value: config, scope: "regular" }}, function() {{}});
    
    chrome.webRequest.onAuthRequired.addListener(
      function(details, callback) {{
        callback({{
          authCredentials: {{
            username: "{PROXY_USER}",
            password: "{PROXY_PASS}"
          }}
        }});
      }},
      {{ urls: ["<all_urls>"] }},
      ["asyncBlocking"]
    );
    '''
    compress_proxy_dir = os.path.join(extension_dir, "proxy/compress")
    os.makedirs(compress_proxy_dir, exist_ok=True)


    save_dir = os.path.join(extension_dir, "proxy.zip")
    # Tạo tệp zip chứa extension
    with zipfile.ZipFile(save_dir, 'w') as zp:
        zp.writestr("manifest.json", manifest_json.strip())
        zp.writestr("background.js", background_js.strip())

    return save_dir


def get_extension_folder(name, proxy: str, extension_dir: str) -> os.path:
    unzip_proxy_dir = os.path.join(extension_dir, "proxy/unzip")
    os.makedirs(unzip_proxy_dir, exist_ok=True)

    with zipfile.ZipFile(create_proxy_extension(name, proxy, extension_dir=extension_dir), 'r') as zip_ref:
        zip_ref.extractall(unzip_proxy_dir)
        zip_ref.close()
    return unzip_proxy_dir

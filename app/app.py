from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory, Response
from flask_login import LoginManager
from functools import wraps
import yaml
from file_watcher import Watcher
import threading
import logging
import sys
import flask.cli
flask.cli.show_server_banner = lambda *args: None
from markupsafe import escape
from constants import *
from settings import *
from db import *
from shop import *
from auth import *
from titles import *
from utils import *
from library import *
import titledb
import os

def init():
    global watcher
    global watcher_thread
    # Create and start the file watcher
    logger.info('Initializing File Watcher...')
    watcher = Watcher(on_library_change)
    watcher_thread = threading.Thread(target=watcher.run)
    watcher_thread.daemon = True
    watcher_thread.start()

    # load initial configuration
    logger.info('Loading initial configuration...')
    reload_conf()

    # Update titledb
    titledb.update_titledb(app_settings)
    load_titledb(app_settings)

os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = OWNFOIL_DB
# TODO: generate random secret_key
app.config['SECRET_KEY'] = '8accb915665f11dfa15c2db1a4e8026905f57716'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

## Global variables
titles_library = []
app_settings = {}
# Create a global variable and lock
scan_in_progress = False
scan_lock = threading.Lock()

# Configure logging
formatter = ColoredFormatter(
    '[%(asctime)s.%(msecs)03d] %(levelname)s (%(module)s) %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)

# Create main logger
logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

# Apply filter to hide date from http access logs
log_werkzeug = logging.getLogger('werkzeug')
log_werkzeug.addFilter(FilterRemoveDateFromWerkzeugLogs())


db.init_app(app)

login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    # since the user_id is just the primary key of our user table, use it in the query for the user
    return User.query.filter_by(id=user_id).first()

app.register_blueprint(auth_blueprint)

with app.app_context():
    db.create_all()
    # init users from ENV
    if os.environ.get('USER_ADMIN_NAME') is not None:
        init_user_from_environment(environment_name="USER_ADMIN", admin=True)
    if os.environ.get('USER_GUEST_NAME') is not None:
        init_user_from_environment(environment_name="USER_GUEST", admin=False)

def tinfoil_error(error):
    return jsonify({
        'error': error
    })

def tinfoil_access(f):
    @wraps(f)
    def _tinfoil_access(*args, **kwargs):
        reload_conf()
        hauth_success = None
        auth_success = None
        request.verified_host = None
        # Host verification to prevent hotlinking
        #Tinfoil doesn't send Hauth for file grabs, only directories, so ignore get_game endpoints.
        host_verification = "/api/get_game" not in request.path and (request.is_secure or request.headers.get("X-Forwarded-Proto") == "https")
        if host_verification:
            request_host = request.host
            request_hauth = request.headers.get('Hauth')
            logger.info(f"Secure Tinfoil request from remote host {request_host}, proceeding with host verification.")
            shop_host = app_settings["shop"].get("host")
            shop_hauth = app_settings["shop"].get("hauth")
            if not shop_host:
                logger.error("Missing shop host configuration, Host verification is disabled.")

            elif request_host != shop_host:
                logger.warning(f"Incorrect URL referrer detected: {request_host}.")
                error = f"Incorrect URL `{request_host}`."
                hauth_success = False

            elif not shop_hauth:
                # Try authentication, if an admin user is logging in then set the hauth
                auth_success, auth_error, auth_is_admin =  basic_auth(request)
                if auth_success and auth_is_admin:
                    shop_settings = app_settings['shop']
                    shop_settings['hauth'] = request_hauth
                    set_shop_settings(shop_settings)
                    logger.info(f"Successfully set Hauth value for host {request_host}.")
                    hauth_success = True
                else:
                    logger.warning(f"Hauth value not set for host {request_host}, Host verification is disabled. Connect to the shop from Tinfoil with an admin account to set it.")

            elif request_hauth != shop_hauth:
                logger.warning(f"Incorrect Hauth detected for host: {request_host}.")
                error = f"Incorrect Hauth for URL `{request_host}`."
                hauth_success = False

            else:
                hauth_success = True
                request.verified_host = shop_host

            if hauth_success is False:
                return tinfoil_error(error)
        
        # Now checking auth if shop is private
        if not app_settings['shop']['public']:
            # Shop is private
            if auth_success is None:
                auth_success, auth_error, _ = basic_auth(request)
            if not auth_success:
                return tinfoil_error(auth_error)
        # Auth success
        return f(*args, **kwargs)
    return _tinfoil_access

def access_shop():
    return render_template('index.html', title='Library', admin_account_created=admin_account_created(), valid_keys=app_settings['titles']['valid_keys'])

@access_required('shop')
def access_shop_auth():
    return access_shop()

@app.route('/')
def index():

    @tinfoil_access
    def access_tinfoil_shop():
        shop = {
            "success": app_settings['shop']['motd']
        }
        
        if request.verified_host is not None:
            # enforce client side host verification
            shop["referrer"] = f"https://{request.verified_host}"
            
        shop["files"] = gen_shop_files(db)

        if app_settings['shop']['encrypt']:
            return Response(encrypt_shop(shop), mimetype='application/octet-stream')

        return jsonify(shop)
    
    if all(header in request.headers for header in TINFOIL_HEADERS):
    # if True:
        logger.info(f"Tinfoil connection from {request.remote_addr}")
        return access_tinfoil_shop()
    
    if not app_settings['shop']['public']:
        return access_shop_auth()
    return access_shop()

@app.route('/settings')
@access_required('admin')
def settings_page():
    with open(os.path.join(TITLEDB_DIR, 'languages.json')) as f:
        languages = json.load(f)
        languages = dict(sorted(languages.items()))
    return render_template(
        'settings.html',
        title='Settings',
        languages_from_titledb=languages,
        admin_account_created=admin_account_created(),
        valid_keys=app_settings['titles']['valid_keys'])

@app.get('/api/settings')
@access_required('admin')
def get_settings_api():
    reload_conf()
    settings = app_settings
    if settings['shop'].get('hauth'):
        settings['shop']['hauth'] = True
    else:
        settings['shop']['hauth'] = False
    return jsonify(settings)

@app.post('/api/settings/titles')
@access_required('admin')
def set_titles_api():
    global titles_library
    settings = request.json
    region = settings['region']
    language = settings['language']
    with open(os.path.join(TITLEDB_DIR, 'languages.json')) as f:
        languages = json.load(f)
        languages = dict(sorted(languages.items()))

    if region not in languages or language not in languages[region]:
        resp = {
            'success': False,
            'errors': [{
                    'path': 'titles',
                    'error': f"The region/language pair {region}/{language} is not available."
                }]
        }
        return jsonify(resp)
    
    set_titles_settings(region, language)
    reload_conf()
    titledb.update_titledb(app_settings)
    load_titledb(app_settings)
    titles_library = generate_library()
    resp = {
        'success': True,
        'errors': []
    } 
    return jsonify(resp)

@app.post('/api/settings/shop')
def set_shop_settings_api():
    data = request.json
    set_shop_settings(data)
    reload_conf()
    resp = {
        'success': True,
        'errors': []
    } 
    return jsonify(resp)

@app.route('/api/settings/library/paths', methods=['GET', 'POST', 'DELETE'])
@access_required('admin')
def library_paths_api():
    global titles_library
    global watcher
    if request.method == 'POST':
        data = request.json
        success, errors = add_library_path_to_settings(data['path'])
        reload_conf()
        resp = {
            'success': success,
            'errors': errors
        }
    elif request.method == 'GET':
        reload_conf()
        resp = {
            'success': True,
            'errors': [],
            'paths': app_settings['library']['paths']
        }    
    elif request.method == 'DELETE':
        data = request.json
        watcher.remove_directory(data['path'])
        success, errors = delete_library_path_from_settings(data['path'])
        if success:
            reload_conf()
            success, errors = delete_files_by_library(data['path'])
            titles_library = generate_library()
        resp = {
            'success': success,
            'errors': errors
        }
    return jsonify(resp)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['keys', 'txt']

@app.post('/api/upload')
@access_required('admin')
def upload_file():
    errors = []
    success = False

    file = request.files['file']
    if file and allowed_file(file.filename):
        # filename = secure_filename(file.filename)
        file.save(KEYS_FILE + '.tmp')
        logger.info(f'Validating {file.filename}...')
        valid = load_keys(KEYS_FILE + '.tmp')
        if valid:
            os.rename(KEYS_FILE + '.tmp', KEYS_FILE)
            success = True
            logger.info('Successfully saved valid keys.txt')
            reload_conf()
            scan_library()
        else:
            os.remove(KEYS_FILE + '.tmp')
            logger.error(f'Invalid keys from {file.filename}')

    resp = {
        'success': success,
        'errors': errors
    } 
    return jsonify(resp)


@app.route('/api/titles', methods=['GET'])
@access_required('shop')
def get_all_titles():
    global titles_library
    if not titles_library:
        titles_library = generate_library()

    return jsonify({
        'total': len(titles_library),
        'games': titles_library
    })

@app.route('/api/titles/<title_id>', methods=['GET'])
@access_required('shop')
def get_title_details(title_id):
    """Get detailed information about a specific title including all associated files"""
    title_id = title_id.upper()
    
    # Get all files for this title (base, updates, DLCs)
    all_files = get_all_title_files(title_id)
    
    if not all_files:
        return jsonify({'error': 'Title not found'}), 404
    
    # Get title info from titledb
    title_info = get_game_info(title_id)
    
    # Organize files by type
    base_files = [f for f in all_files if f['type'] == APP_TYPE_BASE]
    update_files = sorted([f for f in all_files if f['type'] == APP_TYPE_UPD], 
                         key=lambda x: int(x['version']) if x['version'] else 0)
    dlc_files = [f for f in all_files if f['type'] == APP_TYPE_DLC]
    
    # Get version information
    all_versions = get_all_existing_versions(title_id)
    owned_versions = [int(f['version']) for f in update_files if f['version']]
    
    # Get DLC information
    all_dlcs = get_all_existing_dlc(title_id)
    owned_dlcs = [f['app_id'] for f in dlc_files]
    
    # Build response
    response = {
        'title_id': title_id,
        'title_info': title_info,
        'files': {
            'base': base_files,
            'updates': update_files,
            'dlc': dlc_files
        },
        'version_info': {
            'all_versions': all_versions,
            'owned_versions': owned_versions,
            'latest_version': get_game_latest_version(all_versions) if all_versions else None,
            'has_latest': owned_versions and all_versions and max(owned_versions) == get_game_latest_version(all_versions)
        },
        'dlc_info': {
            'all_dlcs': all_dlcs,
            'owned_dlcs': owned_dlcs,
            'has_all_dlcs': all(dlc in owned_dlcs for dlc in all_dlcs)
        },
        'total_size': sum(f['size'] for f in all_files)
    }
    
    return jsonify(response)


@app.route('/api/library/organize/preview', methods=['POST'])
@access_required('admin')
def preview_library_organization_endpoint():
    """Preview library organization changes without applying them"""
    data = request.json
    library_paths = data.get('library_paths', None)
    organize_by_name = data.get('organize_by_name', True)
    
    from library import preview_library_organization
    from titles import get_file_size
    changes, errors = preview_library_organization(library_paths, organize_by_name)
    
    # Calculate total size that will be moved
    total_size = sum(get_file_size(c['old_path']) for c in changes if os.path.exists(c['old_path']))
    
    return jsonify({
        'changes': changes,
        'errors': errors,
        'total_files': len(changes),
        'total_size': total_size
    })


@app.route('/api/library/organize/apply', methods=['POST'])
@access_required('admin')
def apply_library_organization_endpoint():
    """Apply library organization changes"""
    data = request.json
    changes = data.get('changes', [])
    dry_run = data.get('dry_run', False)
    
    if not changes:
        return jsonify({'error': 'No changes provided'}), 400
    
    from library import apply_library_organization
    results = apply_library_organization(changes, dry_run)
    
    # Regenerate library after organization
    if not dry_run and results['success']:
        global titles_library
        titles_library = generate_library()
    
    return jsonify({
        'results': results,
        'total_success': len(results['success']),
        'total_errors': len(results['errors'])
    })


@app.route('/api/library/duplicates', methods=['GET'])
@access_required('admin')
def find_duplicate_updates_endpoint():
    """Find duplicate update files"""
    title_id = request.args.get('title_id', None)
    
    from library import find_duplicate_updates
    duplicates = find_duplicate_updates(title_id)
    
    # Calculate total size that can be freed
    total_size = sum(d['size'] for d in duplicates)
    
    return jsonify({
        'duplicates': duplicates,
        'total_files': len(duplicates),
        'total_size': total_size
    })


@app.route('/api/library/duplicates/delete', methods=['POST'])
@access_required('admin')
def delete_duplicate_updates_endpoint():
    """Delete duplicate update files"""
    data = request.json
    duplicates = data.get('duplicates', [])
    dry_run = data.get('dry_run', False)
    
    if not duplicates:
        return jsonify({'error': 'No duplicates provided'}), 400
    
    from library import delete_duplicate_updates
    results = delete_duplicate_updates(duplicates, dry_run)
    
    # Regenerate library after deletion
    if not dry_run and results['deleted']:
        global titles_library
        titles_library = generate_library()
    
    return jsonify({
        'results': results,
        'total_deleted': len(results['deleted']),
        'total_errors': len(results['errors']),
        'space_freed': sum(d['size'] for d in results['deleted'])
    })


@app.route('/api/get_game/<int:id>')
@tinfoil_access
def serve_game(id):
    filepath = db.session.query(Files.filepath).filter_by(id=id).first()[0]
    filedir, filename = os.path.split(filepath)
    return send_from_directory(filedir, filename)


@debounce(10)
def post_library_change():
    global titles_library
    with app.app_context():
        # remove missing files
        remove_missing_files_from_db()
        # update library
        titles_library = generate_library()


def scan_library():
    logger.info(f'Scanning whole library ...')
    library_paths = app_settings['library']['paths']
    
    if not library_paths:
        logger.info('No library paths configured, nothing to do.')
        return

    for library_path in library_paths:
        start_scan_library_path(library_path, update_library=False)
    
    post_library_change()

def start_scan_library_path(library_path, update_library=True):
    global scan_in_progress
    # Acquire the lock before checking and updating the scan status
    with scan_lock:
        if scan_in_progress:
            logger.info('Scan already in progress')
            return
        # Set the scan status to in progress
        scan_in_progress = True

    scan_library_path(app_settings, library_path)

    # Ensure the scan status is reset to not in progress, even if an error occurs
    with scan_lock:
        scan_in_progress = False

    if update_library:
        post_library_change()


@app.post('/api/library/scan')
@access_required('admin')
def scan_library_api():
    global scan_in_progress
    # Acquire the lock before checking and updating the scan status
    if scan_in_progress:
        logger.info('Scan already in progress')
        resp = {
            'success': False,
            'errors': []
        } 
        return resp
    
    data = request.json
    path = data['path']

    if path is None:
        scan_library()
    else:
        start_scan_library_path(path)

    resp = {
        'success': True,
        'errors': []
    } 
    return jsonify(resp)

def reload_conf():
    global app_settings
    global watcher
    app_settings = load_settings()
    # add library paths to watchdog if necessary
    library_paths = app_settings['library']['paths']
    if library_paths:
        for dir in library_paths:
            watcher.add_directory(dir)


def on_library_change(events):
    with app.app_context():
        created_events = [e for e in events if e.type == 'created']
        modified_events = [e for e in events if e.type != 'created']

        for event in modified_events:
            if event.type == 'moved':
                if file_exists_in_db(event.src_path):
                    # update the path
                    update_file_path(event.directory, event.src_path, event.dest_path)
                else:
                    # add to the database
                    event.src_path = event.dest_path
                    created_events.append(event)

            elif event.type == 'deleted':
                # delete the file from library if it exists
                delete_file_by_filepath(event.src_path)

            elif event.type == 'modified':
                # can happen if file copy has started before the app was running
                identify_files_and_add_to_db(event.directory, [event.src_path])

        if created_events:
            directories = list(set(e.directory for e in created_events))
            for library_path in directories:
                new_files = [e.src_path for e in created_events if e.directory == library_path]
                identify_files_and_add_to_db(library_path, new_files)

    post_library_change()


if __name__ == '__main__':
    logger.info('Starting initialization of Ownfoil...')
    init()
    logger.info('Initialization steps done, starting server...')
    app.run(debug=False, host="0.0.0.0", port=8465)
    # Shutdown server
    logger.info('Shutting down server...')
    watcher.stop()
    watcher_thread.join()
    logger.debug('Watcher thread terminated.')

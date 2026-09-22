import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _load_secret_key():
    env_key = os.environ.get('BIFROST_SECRET_KEY')
    if env_key:
        return env_key
    key_file = BASE_DIR / '.secret_key'
    if key_file.exists():
        return key_file.read_text().strip()
    from django.core.management.utils import get_random_secret_key
    key = get_random_secret_key()
    key_file.write_text(key)
    key_file.chmod(0o600)
    return key


def _lan_ip():
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except OSError:
        return None


SECRET_KEY = _load_secret_key()

# Desenvolvimento local por padrao. O start_public_server.py desliga com BIFROST_DEBUG=0.
DEBUG = os.environ.get('BIFROST_DEBUG', '1').lower() not in ('0', 'false', 'no')

# Hosts aceitos: localhost, o IP da rede local desta maquina e o tunel Cloudflare.
# Outros hosts: BIFROST_ALLOWED_HOSTS="meu.dominio,outro.dominio"
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', '.trycloudflare.com'] + [
    h.strip() for h in os.environ.get('BIFROST_ALLOWED_HOSTS', '').split(',') if h.strip()
]
if _lan_ip():
    ALLOWED_HOSTS.append(_lan_ip())

# Acesso por outras maquinas.
# Atras do tunel Cloudflare o navegador usa HTTPS, mas o Django recebe HTTP em
# 127.0.0.1. Sem esta lista, todo POST (Armazenar, Recuperar, Migrar) falha com
# "403 CSRF verification failed. Origin checking failed".
# Para outro dominio/tunel, defina BIFROST_TRUSTED_ORIGINS="https://meu.dominio,https://outro.dominio"
CSRF_TRUSTED_ORIGINS = [
    'https://*.trycloudflare.com',
] + [o.strip() for o in os.environ.get('BIFROST_TRUSTED_ORIGINS', '').split(',') if o.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'bifrost_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'bifrost_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'bifrost_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

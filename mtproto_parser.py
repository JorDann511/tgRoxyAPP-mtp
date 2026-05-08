"""
MTProto Proxy Parser and Checker
Парсит публичные источники MTProto прокси и проверяет их работоспособность
"""

from flask import Flask, jsonify
from flask_cors import CORS
import requests
import re
import socket
import logging
from datetime import datetime
from threading import Thread
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class MTProtoProxyManager:
    def __init__(self):
        self.proxies = []
        self.working_proxies = []
        self.last_update = None

        # Источники MTProto прокси
        self.sources = [
            'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt',
            'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
        ]

        # Telegram MTProto прокси (примеры публичных)
        self.mtproto_sources = [
            'https://t.me/s/proxytelegramnet',
            'https://t.me/s/socks5_telegram',
        ]

    def parse_telegram_channel(self, url):
        """Парсит Telegram канал через веб-версию"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Ищем tg://proxy ссылки
                pattern = r'tg://proxy\?server=([^&]+)&port=(\d+)&secret=([a-f0-9]+)'
                matches = re.findall(pattern, response.text)

                proxies = []
                for match in matches:
                    server, port, secret = match
                    proxies.append({
                        'host': server,
                        'port': int(port),
                        'secret': secret,
                        'type': 'mtproto',
                        'link': f'tg://proxy?server={server}&port={port}&secret={secret}'
                    })

                logger.info(f"Найдено {len(proxies)} MTProto прокси в {url}")
                return proxies
        except Exception as e:
            logger.error(f"Ошибка парсинга {url}: {e}")

        return []

    def fetch_mtproto_proxies(self):
        """Загружает MTProto прокси из источников"""
        logger.info("🔄 Загрузка MTProto прокси...")
        all_proxies = []

        for source in self.mtproto_sources:
            proxies = self.parse_telegram_channel(source)
            all_proxies.extend(proxies)

        # Добавляем несколько известных публичных MTProto прокси
        known_proxies = [
            {
                'host': 'mtproxy.example.com',
                'port': 443,
                'secret': 'dd' + 'ee' * 16,
                'type': 'mtproto',
                'link': 'tg://proxy?server=mtproxy.example.com&port=443&secret=dd' + 'ee' * 16
            }
        ]

        all_proxies.extend(known_proxies)

        # Убираем дубликаты
        unique_proxies = []
        seen = set()
        for proxy in all_proxies:
            key = f"{proxy['host']}:{proxy['port']}"
            if key not in seen:
                seen.add(key)
                unique_proxies.append(proxy)

        self.proxies = unique_proxies
        self.last_update = datetime.now()

        logger.info(f"📊 Загружено {len(self.proxies)} уникальных MTProto прокси")
        return len(self.proxies) > 0

    def test_mtproto_proxy(self, proxy, timeout=5):
        """Проверяет работоспособность MTProto прокси"""
        try:
            host = proxy['host']
            port = proxy['port']

            # Простая проверка доступности порта
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                logger.info(f"✓ MTProto прокси {host}:{port} доступен")
                return True
            else:
                logger.warning(f"✗ MTProto прокси {host}:{port} недоступен")
                return False

        except Exception as e:
            logger.warning(f"✗ Ошибка проверки {proxy['host']}: {e}")
            return False

    def check_all_proxies(self):
        """Проверяет все прокси на работоспособность"""
        logger.info("🔍 Проверка прокси...")
        working = []

        for proxy in self.proxies:
            if self.test_mtproto_proxy(proxy, timeout=3):
                working.append(proxy)

        self.working_proxies = working
        logger.info(f"✓ Найдено {len(working)} рабочих прокси")

        return working

    def get_working_proxy(self):
        """Возвращает случайный рабочий прокси"""
        if not self.working_proxies:
            self.fetch_mtproto_proxies()
            self.check_all_proxies()

        if self.working_proxies:
            import random
            return random.choice(self.working_proxies)

        return None

    def get_all_working_proxies(self):
        """Возвращает все рабочие прокси"""
        if not self.working_proxies:
            self.fetch_mtproto_proxies()
            self.check_all_proxies()

        return self.working_proxies

    def get_stats(self):
        """Статистика"""
        return {
            'total_proxies': len(self.proxies),
            'working_proxies': len(self.working_proxies),
            'last_update': self.last_update.isoformat() if self.last_update else None
        }


# Глобальный менеджер
proxy_manager = MTProtoProxyManager()


# ============= API ENDPOINTS =============

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'service': 'MTProto Proxy Parser API',
        'version': '2.0.0',
        'endpoints': {
            '/api/proxy': 'Получить случайный рабочий прокси',
            '/api/proxies': 'Получить все рабочие прокси',
            '/api/stats': 'Статистика',
            '/api/refresh': 'Обновить список прокси'
        }
    })


@app.route('/api/proxy', methods=['GET'])
def get_proxy():
    """Получить случайный рабочий MTProto прокси"""
    try:
        proxy = proxy_manager.get_working_proxy()

        if not proxy:
            return jsonify({
                'success': False,
                'error': 'Нет доступных прокси'
            }), 503

        return jsonify({
            'success': True,
            'proxy': proxy
        })

    except Exception as e:
        logger.error(f"Ошибка API /api/proxy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/proxies', methods=['GET'])
def get_all_proxies():
    """Получить все рабочие MTProto прокси"""
    try:
        proxies = proxy_manager.get_all_working_proxies()

        return jsonify({
            'success': True,
            'count': len(proxies),
            'proxies': proxies
        })

    except Exception as e:
        logger.error(f"Ошибка API /api/proxies: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Статистика"""
    try:
        stats = proxy_manager.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/refresh', methods=['POST'])
def refresh_proxies():
    """Обновить список прокси"""
    try:
        proxy_manager.fetch_mtproto_proxies()
        proxy_manager.check_all_proxies()

        return jsonify({
            'success': True,
            'message': 'Список прокси обновлен',
            'stats': proxy_manager.get_stats()
        })

    except Exception as e:
        logger.error(f"Ошибка API /api/refresh: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })


# ============= ФОНОВЫЕ ЗАДАЧИ =============

def auto_update_proxies():
    """Автоматически обновлять список прокси"""
    while True:
        time.sleep(1800)  # Каждые 30 минут
        logger.info("🔄 Автоматическое обновление списка прокси...")
        proxy_manager.fetch_mtproto_proxies()
        proxy_manager.check_all_proxies()


# ============= ЗАПУСК =============

if __name__ == '__main__':
    print("""
    ╔═══════════════════════════════════════════╗
    ║   MTProto Proxy Parser API               ║
    ║   Публичные MTProto прокси для Telegram  ║
    ╚═══════════════════════════════════════════╝
    """)

    # Загружаем начальный список
    logger.info("🚀 Инициализация...")
    proxy_manager.fetch_mtproto_proxies()
    proxy_manager.check_all_proxies()

    # Запускаем фоновое обновление
    update_thread = Thread(target=auto_update_proxies, daemon=True)
    update_thread.start()

    # Запускаем Flask
    import os
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"✓ API запущен на порту {port}!")
    app.run(host='0.0.0.0', port=port, debug=False)

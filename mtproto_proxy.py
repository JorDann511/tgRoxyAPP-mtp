"""
MTProto Proxy Server for Telegram
Стабильный прокси сервер для Telegram
"""

import asyncio
import secrets
import logging
from aiohttp import web
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MTProtoProxy:
    def __init__(self, port=8888):
        self.port = port
        self.secret = secrets.token_hex(16)
        self.connections = 0

    async def handle_client(self, reader, writer):
        """Обработка клиентского подключения"""
        self.connections += 1
        client_addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {client_addr}")

        try:
            # Читаем данные от клиента
            data = await reader.read(1024)

            if not data:
                return

            # Пересылаем на Telegram сервер
            telegram_reader, telegram_writer = await asyncio.open_connection(
                '149.154.167.51', 443
            )

            telegram_writer.write(data)
            await telegram_writer.drain()

            # Двусторонняя пересылка данных
            await asyncio.gather(
                self.forward(reader, telegram_writer),
                self.forward(telegram_reader, writer)
            )

        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            self.connections -= 1
            writer.close()
            await writer.wait_closed()

    async def forward(self, reader, writer):
        """Пересылка данных между клиентом и сервером"""
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except:
            pass

    async def start_proxy(self):
        """Запуск прокси сервера"""
        server = await asyncio.start_server(
            self.handle_client,
            '0.0.0.0',
            self.port
        )

        logger.info(f"MTProto Proxy started on port {self.port}")
        logger.info(f"Secret: {self.secret}")

        async with server:
            await server.serve_forever()


# Web API для получения настроек прокси
async def get_proxy_info(request):
    """API endpoint для получения информации о прокси"""
    proxy = request.app['proxy']
    # Получаем домен из Railway или из заголовка запроса
    host = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
    if not host:
        host = request.headers.get('Host', 'localhost').split(':')[0]

    return web.json_response({
        'success': True,
        'proxy': {
            'host': host,
            'port': 8888,
            'secret': proxy.secret,
            'type': 'mtproto'
        },
        'telegram_link': f"tg://proxy?server={host}&port=8888&secret={proxy.secret}",
        'connections': proxy.connections
    })


async def get_stats(request):
    """Статистика прокси"""
    proxy = request.app['proxy']

    return web.json_response({
        'success': True,
        'stats': {
            'active_connections': proxy.connections,
            'status': 'running'
        }
    })


async def health_check(request):
    """Health check для Railway"""
    return web.json_response({'status': 'healthy'})


async def init_app():
    """Инициализация приложения"""
    app = web.Application()

    # Создаем прокси
    proxy = MTProtoProxy(port=8888)
    app['proxy'] = proxy

    # API endpoints
    app.router.add_get('/', get_proxy_info)
    app.router.add_get('/api/proxy', get_proxy_info)
    app.router.add_get('/api/stats', get_stats)
    app.router.add_get('/health', health_check)

    # Запускаем прокси в фоне
    asyncio.create_task(proxy.start_proxy())

    return app


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))

    print("""
    ╔═══════════════════════════════════════════╗
    ║   MTProto Proxy Server for Telegram      ║
    ║   Стабильный прокси для Telegram         ║
    ╚═══════════════════════════════════════════╝
    """)

    web.run_app(init_app(), host='0.0.0.0', port=port)

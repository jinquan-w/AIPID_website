"""
AIPID 温控系统 - WSGI 入口
Gunicorn 通过此文件加载应用:
    gunicorn -c gunicorn.conf.py wsgi:app
"""
from app import app

if __name__ == '__main__':
    app.run()

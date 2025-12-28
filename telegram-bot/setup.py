from setuptools import setup, find_packages

setup(
    name="tg_bot_for_clients_lb",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot",
        "mysql-connector-python",
        "python-dotenv",
        "pycryptodome",
    ],
)

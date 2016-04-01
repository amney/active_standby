from setuptools import setup

setup(
    name='active_standby',
    version='0.0.1',
    packages=[''],
    url='https://github.com/amney/active_standby',
    license='Apache 2.0',
    author='Tim Garner',
    author_email='tigarner@cisco.com',
    description='Dynamically enable a standby port channel when the active port channel goes down',
    install_requires=[
        'click',
        'requests',
        'websocket-client'
    ]
)

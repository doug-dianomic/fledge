from setuptools import setup, find_packages

setup(
    name='Fledge',
    python_requires='~=3.5',
    version='0.1',
    description='Fledge',
    url='http://github.com/fledge/Fledge',
    author='OSIsoft, LLC',
    author_email='info@dianomic.com',
    license='Apache 2.0',
    # TODO: list of excludes (tests)
    packages=find_packages(),
    entry_points={
        'console_scripts': [],
    },
    zip_safe=False
)

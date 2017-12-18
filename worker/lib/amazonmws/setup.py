from setuptools import setup


def readme():
      with open('README.rst') as f:
            return f.read()


setup(name='amazonmws',
      version='0.1',
      description='Tools for communicating with Amazon\'s Merchant Web Services (MWS) API.',
      long_description=readme(),
      url='https://github.com/garrettmk/amazonmws',
      author='Garrett Myrick',
      license='MIT',
      packages=['amazonmws'],
      install_requires=[
            'hmac',
            'urllib',
            'base64',
            'functools',
            'hashlib',
            'time'
      ],
      zip_safe=False,
      include_package_data=True,
      keywords='amazon mws advertising')
from setuptools import setup, find_packages

setup(
    name='django_swiftapi',
    version='0.1.12',
    description='Easy to use django package for building APIs quicker than ever, built on top of django-ninja-extra',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Md Sohanur Khan Sagor',
    author_email='guy04473@gmail.com',
    url='https://github.com/deepdiverguy/django_swiftapi',
    packages=find_packages(),  # Automatically find packages in folder
    install_requires=[
        'django',
        'django-ninja',
        'ninja-schema',
        'django-ninja-extra',
        'asgiref',
        'Pillow',
    ],
    # entry_points={
    #     'console_scripts': [
    #         'django_swiftapi = django_swiftapi.cli:main',
    #     ],
    # },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.7',
)

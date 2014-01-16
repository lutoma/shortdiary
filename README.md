shortdiary
==========

[![Build Status](https://travis-ci.org/shortdiary/shortdiary.png?branch=master)](undefined)

Local (development) Installation
--------------------------------

```
git clone https://github.com/shortdiary/shortdiary.git
cd shortdiary
virtualenv2 .virtualenv --prompt="(shortdiary)"
source .virtualenv/bin/activate
pip install -r requirements.txt
./manage.py syncdb
./manage.py migrate --fake
./manage.py syncdb --all
./manage.py migrate --all
```
As last step, start the local development server using `./manage.py runserver` and point your browser to `http://127.0.0.1:8000`.

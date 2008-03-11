#!/usr/bin/env python
#coding: utf8

# blitiri - A single-file blog engine.
# Alberto Bertogli (albertito@gmail.com)

#
# Configuration section
#
# You can edit these values, or create a file named "config.py" and put them
# there to make updating easier. The ones in config.py take precedence.
#

# Directory where entries are stored
data_path = "/tmp/blog/data"

# Path where templates are stored. Use an empty string for the built-in
# default templates. If they're not found, the built-in ones will be used.
templates_path = "/tmp/blog/templates"

# URL to the blog, including the name. Can be a full URL or just the path.
blog_url = "/blog/blitiri.cgi"

# Style sheet (CSS) URL. Can be relative or absolute. To use the built-in
# default, set it to blog_url + "/style".
css_url = blog_url + "/style"

# Blog title
title = "I don't like blogs"

# Default author
author = "Hartmut Kegan"

# Article encoding
encoding = "utf8"

#
# End of configuration
# DO *NOT* EDIT ANYTHING PAST HERE
#


import sys
import os
import time
import datetime
import calendar
import zlib
import urllib
import cgi
from docutils.core import publish_parts

# Load the config file, if there is one
try:
	from config import *
except:
	pass


# Default template

default_main_header = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">

<html>
<head>
<link rel="alternate" title="%(title)s" href="%(fullurl)s/atom"
	type="application/atom+xml" />
<link href="%(css_url)s" rel="stylesheet"
	type="text/css" />
<title>%(title)s</title>
</head>

<body>

<h1><a href="%(url)s">%(title)s</a></h1>

<div class="content">
"""

default_main_footer = """
</div><p/>
<hr/><br/>
<div class="footer">
  %(showyear)s: %(monthlinks)s<br/>
  years: %(yearlinks)s<br/>
  subscribe: <a href="%(url)s/atom">atom</a><br/>
  views: <a href="%(url)s/">blog</a> <a href="%(url)s/list">list</a><br/>
</div>

</body>
</html>
"""

default_article_header = """
<div class="article">
<h2><a href="%(url)s/post/%(uuid)s">%(arttitle)s</a></h2>
<span class="artinfo">
  by %(author)s on <span class="date">

<a class="date" href="%(url)s/%(cyear)d/">%(cyear)04d</a>-\
<a class="date" href="%(url)s/%(cyear)d/%(cmonth)d/">%(cmonth)02d</a>-\
<a class="date" href="%(url)s/%(cyear)d/%(cmonth)d/%(cday)d/">%(cday)02d</a>\
    %(chour)02d:%(cminute)02d</span>
  (updated on <span class="date">
<a class="date" href="%(url)s/%(uyear)d/">%(uyear)04d</a>-\
<a class="date" href="%(url)s/%(uyear)d/%(umonth)d/">%(umonth)02d</a>-\
<a class="date" href="%(url)s/%(uyear)d/%(umonth)d/%(uday)d/">%(uday)02d</a>\
    %(uhour)02d:%(uminute)02d)</span><br/>
  <span class="tags">tagged %(tags)s</span>
</span><br/>
<p/>
<div class="artbody">
"""

default_article_footer = """
<p/>
</div>
</div>
"""

# Default CSS
default_css = """
body {
	font-family: sans-serif;
	font-size: small;
}

div.content {
	width: 50%;
}

h1 {
	font-size: large;
	border-bottom: 2px solid #99F;
	width: 60%;
	margin-bottom: 1em;
}

h2 {
	font-size: medium;
	font-weigth: none;
	margin-bottom: 1pt;
	border-bottom: 1px solid #99C;
}

h1 a, h2 a {
	text-decoration: none;
	color: black;
}

span.artinfo {
	font-size: xx-small;
}

span.artinfo a {
	text-decoration: none;
	color: #339;
}

span.artinfo a:hover {
	text-decoration: none;
	color: blue;
}

div.artbody {
	margin-left: 1em;
}

div.article {
	margin-bottom: 2em;
}

hr {
	float: left;
	height: 2px;
	border: 0;
	background-color: #99F;
	width: 60%;
}

div.footer {
	font-size: x-small;
}

div.footer a {
	text-decoration: none;
}

/* Articles are enclosed in <div class="section"> */
div.section h1 {
	font-size: small;
	font-weigth: none;
	width: 100%;
	margin-bottom: 1pt;
	border-bottom: 1px dotted #99C;
}

"""

# find out our URL, needed for syndication
try:
	n = os.environ['SERVER_NAME']
	p = os.environ['SERVER_PORT']
	s = os.environ['SCRIPT_NAME']
	if p == '80': p = ''
	else: p = ':' + p
	full_url = 'http://%s%s%s' % (n, p, s)
except KeyError:
	full_url = 'Not needed'


class Templates (object):
	def __init__(self, tpath, db, showyear = None):
		self.tpath = tpath
		self.db = db
		now = datetime.datetime.now()
		if not showyear:
			showyear = now.year

		self.vars = {
			'css_url': css_url,
			'title': title,
			'url': blog_url,
			'fullurl': full_url,
			'year': now.year,
			'month': now.month,
			'day': now.day,
			'showyear': showyear,
			'monthlinks': ' '.join(db.get_month_links(showyear)),
			'yearlinks': ' '.join(db.get_year_links()),
		}

	def get_main_header(self):
		p = self.tpath + '/header.html'
		if os.path.isfile(p):
			return open(p).read() % self.vars
		return default_main_header % self.vars

	def get_main_footer(self):
		p = self.tpath + '/footer.html'
		if os.path.isfile(p):
			return open(p).read() % self.vars
		return default_main_footer % self.vars

	def get_article_header(self, article):
		avars = self.vars.copy()
		avars.update( {
			'arttitle': article.title,
			'author': article.author,
			'date': article.created.isoformat(' '),
			'uuid': article.uuid,
			'created': article.created.isoformat(' '),
			'updated': article.updated.isoformat(' '),
			'tags': article.get_tags_links(),

			'cyear': article.created.year,
			'cmonth': article.created.month,
			'cday': article.created.day,
			'chour': article.created.hour,
			'cminute': article.created.minute,
			'csecond': article.created.second,

			'uyear': article.updated.year,
			'umonth': article.updated.month,
			'uday': article.updated.day,
			'uhour': article.updated.hour,
			'uminute': article.updated.minute,
			'usecond': article.updated.second,
		} )

		p = self.tpath + '/art_header.html'
		if os.path.isfile(p):
			return open(p).read() % avars
		return default_article_header % avars

	def get_article_footer(self, article):
		avars = self.vars.copy()
		avars.update( {
			'arttitle': article.title,
			'author': article.author,
			'date': article.created.isoformat(' '),
			'uuid': article.uuid,
			'created': article.created.isoformat(' '),
			'updated': article.updated.isoformat(' '),
			'tags': article.get_tags_links(),

			'cyear': article.created.year,
			'cmonth': article.created.month,
			'cday': article.created.day,
			'chour': article.created.hour,
			'cminute': article.created.minute,
			'csecond': article.created.second,

			'uyear': article.updated.year,
			'umonth': article.updated.month,
			'uday': article.updated.day,
			'uhour': article.updated.hour,
			'uminute': article.updated.minute,
			'usecond': article.updated.second,
		} )

		p = self.tpath + '/art_footer.html'
		if os.path.isfile(p):
			return open(p).read() % avars
		return default_article_footer % avars


class Article (object):
	def __init__(self, path):
		self.path = path
		self.created = None
		self.updated = None
		self.uuid = "%08x" % zlib.crc32(self.path)

		self.loaded = False

		# loaded on demand
		self._title = 'Removed post'
		self._author = author
		self._tags = []
		self._raw_content = ''


	def get_title(self):
		if not self.loaded:
			self.load()
		return self._title
	title = property(fget = get_title)

	def get_author(self):
		if not self.loaded:
			self.load()
		return self._author
	author = property(fget = get_author)

	def get_tags(self):
		if not self.loaded:
			self.load()
		return self._tags
	tags = property(fget = get_tags)

	def get_raw_content(self):
		if not self.loaded:
			self.load()
		return self._raw_content
	raw_content = property(fget = get_raw_content)


	def __cmp__(self, other):
		if self.path == other.path:
			return 0
		if not self.created:
			return 1
		if not other.created:
			return -1
		if self.created < other.created:
			return -1
		return 1

	def title_cmp(self, other):
		return cmp(self.title, other.title)


	def load(self):
		try:
			raw = open(data_path + '/' + self.path).readlines()
		except:
			return

		count = 0
		for l in raw:
			if ':' in l:
				name, value = l.split(':', 1)
				if name.lower() == 'title':
					self._title = value
				elif name.lower() == 'author':
					self._author = value
				elif name.lower() == 'tags':
					ts = value.split(',')
					ts = [t.strip() for t in ts]
					self._tags = set(ts)
			elif l == '\n':
				# end of header
				break
			count += 1
		self._raw_content = ''.join(raw[count + 1:])
		self.loaded = True

	def to_html(self):
		try:
			raw = open(data_path + '/' + self.path).readlines()
		except:
			return "Can't open post file<p>"
		raw = raw[raw.index('\n'):]

		settings = {
			'input_encoding': encoding,
			'output_encoding': 'utf8',
		}
		parts = publish_parts(self.raw_content,
				settings_overrides = settings,
				writer_name = "html")
		return parts['body'].encode('utf8')

	def get_tags_links(self):
		l = []
		tags = list(self.tags)
		tags.sort()
		for t in tags:
			l.append('<a class="tag" href="%s/tag/%s">%s</a>' % \
				(blog_url, urllib.quote(t), t) )
		return ', '.join(l)


class DB (object):
	def __init__(self, dbpath):
		self.dbpath = dbpath
		self.articles = []
		self.uuids = {}
		self.actyears = set()
		self.actmonths = set()
		self.load()

	def get_articles(self, year = 0, month = 0, day = 0, tags = None):
		l = []
		for a in self.articles:
			if year and a.created.year != year: continue
			if month and a.created.month != month: continue
			if day and a.created.day != day: continue
			if tags and not tags.issubset(a.tags): continue

			l.append(a)

		return l

	def get_article(self, uuid):
		return self.uuids[uuid]

	def load(self):
		try:
			f = open(self.dbpath)
		except:
			return

		for l in f:
			# Each line has the following comma separated format:
			# path (relative to data_path), \
			#	created (epoch), \
			# 	updated (epoch)
			try:
				l = l.split(',')
			except:
				continue

			a = Article(l[0])
			a.created = datetime.datetime.fromtimestamp(
						float(l[1]) )
			a.updated = datetime.datetime.fromtimestamp(
						float(l[2]))
			self.uuids[a.uuid] = a
			self.actyears.add(a.created.year)
			self.actmonths.add((a.created.year, a.created.month))
			self.articles.append(a)

	def save(self):
		f = open(self.dbpath + '.tmp', 'w')
		for a in self.articles:
			s = ''
			s += a.path + ', '
			s += str(time.mktime(a.created.timetuple())) + ', '
			s += str(time.mktime(a.updated.timetuple())) + '\n'
			f.write(s)
		f.close()
		os.rename(self.dbpath + '.tmp', self.dbpath)

	def get_year_links(self):
		yl = list(self.actyears)
		yl.sort(reverse = True)
		return [ '<a href="%s/%d/">%d</a>' % (blog_url, y, y)
				for y in yl ]

	def get_month_links(self, year):
		am = [ i[1] for i in self.actmonths if i[0] == year ]
		ml = []
		for i in range(1, 13):
			name = calendar.month_name[i][:3]
			if i in am:
				s = '<a href="%s/%d/%d/">%s</a>' % \
					( blog_url, year, i, name )
			else:
				s = name
			ml.append(s)
		return ml

#
# Main
#


def render_html(articles, db, actyear = None):
	template = Templates(templates_path, db, actyear)
	print 'Content-type: text/html; charset=utf-8\n'
	print template.get_main_header()
	for a in articles:
		print template.get_article_header(a)
		print a.to_html()
		print template.get_article_footer(a)
	print template.get_main_footer()

def render_artlist(articles, db, actyear = None):
	template = Templates(templates_path, db, actyear)
	print 'Content-type: text/html; charset=utf-8\n'
	print template.get_main_header()
	print '<h2>Articles</h2>'
	for a in articles:
		print '<li><a href="%(url)s/uuid/%(uuid)s">%(title)s</a></li>' \
			% {	'url': blog_url,
				'uuid': a.uuid,
				'title': a.title,
				'author': a.author,
			}
	print template.get_main_footer()

def render_atom(articles):
	if len(articles) > 0:
		updated = articles[0].updated.isoformat()
	else:
		updated = datetime.datetime.now().isoformat()

	print 'Content-type: application/atom+xml; charset=utf-8\n'
	print """<?xml version="1.0" encoding="utf-8"?>

<feed xmlns="http://www.w3.org/2005/Atom">
 <title>%(title)s</title>
 <link rel="alternate" type="text/html" href="%(url)s"/>
 <link rel="self" type="application/atom+xml" href="%(url)s/atom"/>
 <id>%(url)s</id> <!-- TODO: find a better <id>, see RFC 4151 -->
 <updated>%(updated)sZ</updated>

	""" % {
		'title': title,
		'url': full_url,
		'updated': updated,
	}

	for a in articles:
		print """
  <entry>
    <title>%(arttitle)s</title>
    <author><name>%(author)s</name></author>
    <link href="%(url)s/post/%(uuid)s" />
    <id>%(url)s/post/%(uuid)s</id>
    <summary>%(arttitle)s</summary>
    <published>%(created)sZ</published>
    <updated>%(updated)sZ</updated>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml"><p>
%(contents)s
      </p></div>
    </content>
  </entry>
		""" % {
			'arttitle': a.title,
			'author': a.author,
			'uuid': a.uuid,
			'url': full_url,
			'created': a.created.isoformat(),
			'updated': a.updated.isoformat(),
			'contents': a.to_html(),
		}

	print "</feed>"


def render_style():
	print 'Content-type: text/plain\n'
	print default_css

def handle_cgi():
	import cgitb; cgitb.enable()

	form = cgi.FieldStorage()
	year = int(form.getfirst("year", 0))
	month = int(form.getfirst("month", 0))
	day = int(form.getfirst("day", 0))
	tags = set(form.getlist("tag"))
	uuid = None
	atom = False
	style = False
	post = False
	artlist = False

	if os.environ.has_key('PATH_INFO'):
		path_info = os.environ['PATH_INFO']
		style = path_info == '/style'
		atom = path_info == '/atom'
		tag = path_info.startswith('/tag/')
		post = path_info.startswith('/post/')
		artlist = path_info.startswith('/list')
		if not style and not atom and not post and not tag \
				and not artlist:
			date = path_info.split('/')[1:]
			try:
				if len(date) > 1 and date[0]:
					year = int(date[0])
				if len(date) > 2 and date[1]:
					month = int(date[1])
				if len(date) > 3 and date[2]:
					day = int(date[2])
			except ValueError:
				pass
		elif post:
			uuid = path_info.replace('/post/', '')
			uuid = uuid.replace('/', '')
		elif tag:
			t = path_info.replace('/tag/', '')
			t = t.replace('/', '')
			t = urllib.unquote_plus(t)
			tags = set((t,))

	db = DB(data_path + '/db')
	if atom:
		articles = db.get_articles(tags = tags)
		articles.sort(reverse = True)
		render_atom(articles[:10])
	elif style:
		render_style()
	elif post:
		render_html( [db.get_article(uuid)], db, year )
	elif artlist:
		articles = db.get_articles()
		articles.sort(cmp = Article.title_cmp)
		render_artlist(articles, db)
	else:
		articles = db.get_articles(year, month, day, tags)
		articles.sort(reverse = True)
		if not year and not month and not day and not tags:
			articles = articles[:10]
		render_html(articles, db, year)


def usage():
	print 'Usage: %s {add|rm|update} article_path' % sys.argv[0]

def handle_cmd():
	if len(sys.argv) != 3:
		usage()
		return 1

	cmd = sys.argv[1]
	art_path = os.path.realpath(sys.argv[2])

	if os.path.commonprefix([data_path, art_path]) != data_path:
		print "Error: article (%s) must be inside data_path (%s)" % \
				(art_path, data_path)
		return 1
	art_path = art_path[len(data_path):]

	if not os.path.isfile(data_path + '/db'):
		open(data_path + '/db', 'w').write('')
	db = DB(data_path + '/db')

	if cmd == 'add':
		article = Article(art_path)
		for a in db.articles:
			if a == article:
				print 'Error: article already exists'
				return 1
		db.articles.append(article)
		article.created = datetime.datetime.now()
		article.updated = datetime.datetime.now()
		db.save()
	elif cmd == 'rm':
		article = Article(art_path)
		for a in db.articles:
			if a == article:
				break
		else:
			print "Error: no such article"
			return 1
		db.articles.remove(a)
		db.save()
	elif cmd == 'update':
		article = Article(art_path)
		for a in db.articles:
			if a == article:
				break
		else:
			print "Error: no such article"
			return 1
		a.updated = datetime.datetime.now()
		db.save()
	else:
		usage()
		return 1

	return 0


if os.environ.has_key('GATEWAY_INTERFACE'):
	handle_cgi()
else:
	sys.exit(handle_cmd())



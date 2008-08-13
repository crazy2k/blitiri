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

# Are comments allowed? (if False, comments_path option is not used)
enable_comments = False

# Directory where comments are stored (must be writeable by the web server)
comments_path = "/tmp/blog/comments"

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

# Captcha class
class Captcha (object):
	def __init__(self, article):
		self.article = article
		words = article.title.split()
		self.nword = hash(article.title) % len(words) % 5
		self.answer = words[self.nword]
		self.help = 'gotcha, damn spam bot!'

	def get_puzzle(self):
		nword = self.nword + 1
		if nword == 1:
			n = '1st'
		elif nword == 2:
			n = '2nd'
		elif nword == 3:
			n = '3rd'
		else:
			n = str(nword) + 'th'
		return "enter the %s word of the article's title" % n
	puzzle = property(fget = get_puzzle)

	def validate(self, form_data):
		if form_data.captcha.lower() == self.answer.lower():
			return True
		return False


#
# End of configuration
# DO *NOT* EDIT ANYTHING PAST HERE
#


import sys
import os
import errno
import shutil
import time
import datetime
import calendar
import zlib
import urllib
import cgi
from docutils.core import publish_parts
from docutils.utils import SystemMessage

# Before importing the config, add our cwd to the Python path
sys.path.append(os.getcwd())

# Load the config file, if there is one
try:
	from config import *
except:
	pass


# Pimp *_path config variables to support relative paths
data_path = os.path.realpath(data_path)
templates_path = os.path.realpath(templates_path)

# Default template

default_main_header = """\
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
          "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">

<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
<head>
<link rel="alternate" title="%(title)s" href="%(fullurl)s/atom"
	type="application/atom+xml" />
<link href="%(css_url)s" rel="stylesheet" type="text/css" />
<title>%(title)s</title>
</head>

<body>

<h1><a href="%(url)s">%(title)s</a></h1>

<div class="content">
"""

default_main_footer = """
</div>
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
  <span class="tags">tagged %(tags)s</span> -
  <span class="comments">with %(comments)s
    <a href="%(url)s/post/%(uuid)s#comments">comment(s)</a></span>
</span><br/>
<p/>
<div class="artbody">
"""

default_article_footer = """
<p/>
</div>
</div>
"""

default_comment_header = """
<div class="comment">
<a name="comment-%(number)d" />
<h3><a href="#comment-%(number)d">Comment #%(number)d</a></h3>
<span class="cominfo">by %(linked_author)s
  on %(year)04d-%(month)02d-%(day)02d %(hour)02d:%(minute)02d</span>
<p/>
<div class="combody">
"""

default_comment_footer = """
<p/>
</div>
</div>
"""

default_comment_form = """
<div class="comform">
<a name="comment" />
<h3 class="comform"><a href="#comment">Your comment</a></h3>
<div class="comforminner">
<form method="%(form_method)s" action="%(form_action)s">
<div class="comformauthor">
  <label for="comformauthor">Your name %(form_author_error)s</label>
  <input type="text" class="comformauthor" id="comformauthor"
         name="comformauthor" value="%(form_author)s" />
</div>
<div class="comformlink">
  <label for="comformlink">Your link
    <span class="comformoptional">(optional, will be published)</span>
      %(form_link_error)s</label>
  <input type="text" class="comformlink" id="comformlink"
         name="comformlink" value="%(form_link)s" />
  <div class="comformhelp">
    like <span class="formurlexample">http://www.example.com/</span>
    or <span class="formurlexample">mailto:you@example.com</span>
  </div>
</div>
<div class="comformcaptcha">
  <label for="comformcaptcha">Your humanity proof %(form_captcha_error)s</label>
  <input type="text" class="comformcaptcha" id="comformcaptcha"
         name="comformcaptcha" value="%(form_captcha)s" />
  <div class="comformhelp">%(captcha_puzzle)s</div>
</div>
<div class="comformbody">
  <label for="comformbody" class="comformbody">The comment
    %(form_body_error)s</label>
  <textarea class="comformbody" id="comformbody" name="comformbody" rows="15"
            cols="80">%(form_body)s</textarea>
  <div class="comformhelp">
    in
    <a href="http://docutils.sourceforge.net/docs/user/rst/quickref.html">\
RestructuredText</a> format, please
  </div>
</div>
<div class="comformsend">
  <button type="submit" class="comformsend" id="comformsend" name="comformsend">
    Send comment
  </button>
</div>
</form>
</div>
</div>
"""

default_comment_error = '<span class="comformerror">(%(error)s)</span>'


# Default CSS
default_css = """
body {
	font-family: sans-serif;
	font-size: small;
	width: 52em;
}

div.content {
	width: 96%;
}

h1 {
	font-size: large;
	border-bottom: 2px solid #99F;
	width: 100%;
	margin-bottom: 1em;
}

h2 {
	font-size: medium;
	font-weigth: none;
	margin-bottom: 1pt;
	border-bottom: 1px solid #99C;
}

h3 {
	font-size: small;
	font-weigth: none;
	margin-bottom: 1pt;
	border-bottom: 1px solid #99C;
}

h1 a, h2 a, h3 a {
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

span.cominfo {
	font-size: xx-small;
}

span.cominfo a {
	text-decoration: none;
	color: #339;
}

span.cominfo a:hover {
	text-decoration: none;
	color: blue;
}

div.combody {
	margin-left: 2em;
}

div.comment {
	margin-left: 1em;
	margin-bottom: 1em;
}

div.comforminner {
	margin-left: 2em;
}

div.comform {
	margin-left: 1em;
	margin-bottom: 1em;
}

div.comform label {
	display: block;
	border-bottom: 1px solid #99C;
	margin-top: 0.5em;
	clear: both;
}

div.comform span.comformoptional {
	font-size: xx-small;
	color: #666;
}

div.comform input {
	font-size: small;
	width: 99%;
}

div.comformhelp {
	font-size: xx-small;
	text-align: right;
	float: right;
}

span.formurlexample {
	color: #111;
	background-color: #EEF;
	font-family: monospace;
	padding-left: 0.2em;
	padding-right: 0.2em;
}

textarea.comformbody {
	font-family: monospace;
	font-size: small;
	width: 99%;
	height: 15em;
}

button.comformsend {
	margin-top: 0.5em;
}

span.comformerror {
	color: #900;
	font-size: xx-small;
	margin-left: 0.5em;
}

hr {
	float: left;
	height: 2px;
	border: 0;
	background-color: #99F;
	width: 60%;
}

div.footer {
	margin-top: 1em;
	padding-top: 0.4em;
	width: 100%;
	border-top: 2px solid #99F;
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

# helper functions
def rst_to_html(rst):
	settings = {
		'input_encoding': encoding,
		'output_encoding': 'utf8',
		'halt_level': 1,
		'traceback':  1,
	}
	parts = publish_parts(rst, settings_overrides = settings,
				writer_name = "html")
	return parts['body'].encode('utf8')

def validate_rst(rst):
	try:
		rst_to_html(rst)
		return None
	except SystemMessage, e:
		desc = e.args[0].encode('utf-8') # the error string
		desc = desc[9:] # remove "<string>:"
		line = int(desc[:desc.find(':')]) # get just the line number
		desc = desc[desc.find(')')+2:-1] # remove (LEVEL/N)
		try:
			desc, context = desc.split('\n', 1)
		except ValueError:
			context = ''
		if desc.endswith('.'):
			desc = desc[:-1]
		return (line, desc, context)

def valid_link(link):
	import re
	mail_re = r"^[^ \t\n\r@<>()]+@[a-z0-9][a-z0-9\.\-_]*\.[a-z]+$"
	scheme_re = r'^[a-zA-Z]+:'
	url_re = r'^(?:[a-z0-9\-]+|[a-z0-9][a-z0-9\-\.\_]*\.[a-z]+)' \
			r'(?::[0-9]+)?(?:/.*)?$'
	scheme = ''
	rest = link
	if re.match(scheme_re, link, re.I):
		scheme, rest = link.split(':', 1)
	if (not scheme or scheme == 'mailto') and re.match(mail_re, rest, re.I):
		return 'mailto:' + link
	if not scheme and re.match(url_re, rest, re.I):
		return 'http://' + rest
	if scheme:
		return link
	return None

def sanitize(obj):
	if isinstance(obj, basestring):
		return cgi.escape(obj, True)
	return obj


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

	def get_template(self, page_name, default_template, extra_vars = None):
		if extra_vars is None:
			vars = self.vars
		else:
			vars = self.vars.copy()
			vars.update(extra_vars)

		p = '%s/%s.html' % (self.tpath, page_name)
		if os.path.isfile(p):
			return open(p).read() % vars
		return default_template % vars

	def get_main_header(self):
		return self.get_template('header', default_main_header)

	def get_main_footer(self):
		return self.get_template('footer', default_main_footer)

	def get_article_header(self, article):
		return self.get_template(
			'art_header', default_article_header, article.to_vars())

	def get_article_footer(self, article):
		return self.get_template(
			'art_footer', default_article_footer, article.to_vars())

	def get_comment_header(self, comment):
		vars = comment.to_vars()
		if comment.link:
			vars['linked_author'] = '<a href="%s">%s</a>' \
					% (comment.link, comment.author)
		else:
			vars['linked_author'] = comment.author
		return self.get_template(
			'com_header', default_comment_header, vars)

	def get_comment_footer(self, comment):
		return self.get_template(
			'com_footer', default_comment_footer, comment.to_vars())

	def get_comment_form(self, article, form_data, captcha_puzzle):
		vars = article.to_vars()
		vars.update(form_data.to_vars(self))
		vars['captcha_puzzle'] = captcha_puzzle
		return self.get_template(
			'com_form', default_comment_form, vars)

	def get_comment_error(self, error):
		return self.get_template(
			'com_error', default_comment_error, dict(error=error))


class CommentFormData (object):
	def __init__(self, author = '', link = '', captcha = '', body = ''):
		self.author = author
		self.link = link
		self.captcha = captcha
		self.body = body
		self.author_error = ''
		self.link_error = ''
		self.captcha_error = ''
		self.body_error = ''
		self.action = ''
		self.method = 'post'

	def to_vars(self, template):
		render_error = template.get_comment_error
		a_error = self.author_error and render_error(self.author_error)
		l_error = self.link_error and render_error(self.link_error)
		c_error = self.captcha_error \
				and render_error(self.captcha_error)
		b_error = self.body_error and render_error(self.body_error)
		return {
			'form_author': sanitize(self.author),
			'form_link': sanitize(self.link),
			'form_captcha': sanitize(self.captcha),
			'form_body': sanitize(self.body),

			'form_author_error': a_error,
			'form_link_error': l_error,
			'form_captcha_error': c_error,
			'form_body_error': b_error,

			'form_action': self.action,
			'form_method': self.method,
		}


class Comment (object):
	def __init__(self, article, number, created = None):
		self.article = article
		self.number = number
		if created is None:
			self.created = datetime.datetime.now()
		else:
			self.created = created

		self.loaded = False

		# loaded on demand
		self._author = author
		self._link = ''
		self._raw_content = 'Removed comment'


	def get_author(self):
		if not self.loaded:
			self.load()
		return self._author
	author = property(fget = get_author)

	def get_link(self):
		if not self.loaded:
			self.load()
		return self._link
	link = property(fget = get_link)

	def get_raw_content(self):
		if not self.loaded:
			self.load()
		return self._raw_content
	raw_content = property(fget = get_raw_content)


	def set(self, author, raw_content, link = '', created = None):
		self.loaded = True
		self._author = author
		self._raw_content = raw_content
		self._link = link
		self.created = created or datetime.datetime.now()


	def load(self):
		filename = os.path.join(comments_path, self.article.uuid,
					str(self.number))
		try:
			raw = open(filename).readlines()
		except:
			return

		count = 0
		for l in raw:
			if ':' in l:
				name, value = l.split(':', 1)
				if name.lower() == 'author':
					self._author = value.strip()
				elif name.lower() == 'link':
					self._link = value.strip()
			elif l == '\n':
				# end of header
				break
			count += 1
		self._raw_content = ''.join(raw[count + 1:])
		self.loaded = True

	def save(self):
		filename = os.path.join(comments_path, self.article.uuid,
					str(self.number))
		try:
			f = open(filename, 'w')
			f.write('Author: %s\n' % self.author)
			f.write('Link: %s\n' % self.link)
			f.write('\n')
			f.write(self.raw_content)
		except:
			return


	def to_html(self):
		return rst_to_html(self.raw_content)

	def to_vars(self):
		return {
			'number': self.number,
			'author': sanitize(self.author),
			'link': sanitize(self.link),
			'date': self.created.isoformat(' '),
			'created': self.created.isoformat(' '),

			'year': self.created.year,
			'month': self.created.month,
			'day': self.created.day,
			'hour': self.created.hour,
			'minute': self.created.minute,
			'second': self.created.second,
		}

class CommentDB (object):
	def __init__(self, article):
		self.path = os.path.join(comments_path, article.uuid)
		self.comments = []
		self.load(article)

	def load(self, article):
		try:
			f = open(os.path.join(self.path, 'db'))
		except:
			return

		for l in f:
			# Each line has the following comma separated format:
			# number, created (epoch)
			# Empty lines are meaningful and represent removed
			# comments (so we can preserve the comment number)
			l = l.split(',')
			try:
				n = int(l[0])
				d = datetime.datetime.fromtimestamp(float(l[1]))
			except:
				# Removed/invalid comment
				self.comments.append(None)
				continue
			self.comments.append(Comment(article, n, d))

	def save(self):
		old_db = os.path.join(self.path, 'db')
		new_db = os.path.join(self.path, 'db.tmp')
		f = open(new_db, 'w')
		for c in self.comments:
			s = ''
			if c is not None:
				s = ''
				s += str(c.number) + ', '
				s += str(time.mktime(c.created.timetuple()))
			s += '\n'
			f.write(s)
		f.close()
		os.rename(new_db, old_db)


class Article (object):
	def __init__(self, path, created = None, updated = None):
		self.path = path
		self.created = created
		self.updated = updated
		self.uuid = "%08x" % zlib.crc32(self.path)

		self.loaded = False

		# loaded on demand
		self._title = 'Removed post'
		self._author = author
		self._tags = []
		self._raw_content = ''
		self._comments = []


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

	def get_comments(self):
		if not self.loaded:
			self.load()
		return self._comments
	comments = property(fget = get_comments)


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


	def add_comment(self, author, raw_content, link = ''):
		c = Comment(self, len(self.comments))
		c.set(author, raw_content, link)
		self.comments.append(c)
		return c


	def load(self):
		# XXX this tweak is only needed for old DB format, where
		# article's paths started with a slash
		path = self.path
		if path.startswith('/'):
			path = path[1:]
		filename = os.path.join(data_path, path)
		try:
			raw = open(filename).readlines()
		except:
			return

		count = 0
		for l in raw:
			if ':' in l:
				name, value = l.split(':', 1)
				if name.lower() == 'title':
					self._title = value.strip()
				elif name.lower() == 'author':
					self._author = value.strip()
				elif name.lower() == 'tags':
					ts = value.split(',')
					ts = [t.strip() for t in ts]
					self._tags = set(ts)
			elif l == '\n':
				# end of header
				break
			count += 1
		self._raw_content = ''.join(raw[count + 1:])
		db = CommentDB(self)
		self._comments = db.comments
		self.loaded = True

	def to_html(self):
		return rst_to_html(self.raw_content)

	def to_vars(self):
		return {
			'arttitle': sanitize(self.title),
			'author': sanitize(self.author),
			'date': self.created.isoformat(' '),
			'uuid': self.uuid,
			'tags': self.get_tags_links(),
			'comments': len(self.comments),

			'created': self.created.isoformat(' '),
			'ciso': self.created.isoformat(),
			'cyear': self.created.year,
			'cmonth': self.created.month,
			'cday': self.created.day,
			'chour': self.created.hour,
			'cminute': self.created.minute,
			'csecond': self.created.second,

			'updated': self.updated.isoformat(' '),
			'uiso': self.updated.isoformat(),
			'uyear': self.updated.year,
			'umonth': self.updated.month,
			'uday': self.updated.day,
			'uhour': self.updated.hour,
			'uminute': self.updated.minute,
			'usecond': self.updated.second,
		}

	def get_tags_links(self):
		l = []
		tags = list(self.tags)
		tags.sort()
		for t in tags:
			l.append('<a class="tag" href="%s/tag/%s">%s</a>' % \
				(blog_url, urllib.quote(t), sanitize(t) ))
		return ', '.join(l)


class ArticleDB (object):
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

			a = Article(l[0],
				datetime.datetime.fromtimestamp(float(l[1])),
				datetime.datetime.fromtimestamp(float(l[2])))
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

def render_comments(article, template, form_data):
	print '<a name="comments" />'
	for c in article.comments:
		if c is None:
			continue
		print template.get_comment_header(c)
		print c.to_html()
		print template.get_comment_footer(c)
	if not form_data:
		form_data = CommentFormData()
	form_data.action = blog_url + '/comment/' + article.uuid + '#comment'
	captcha = Captcha(article)
	print template.get_comment_form(article, form_data, captcha.puzzle)

def render_html(articles, db, actyear = None, show_comments = False,
		redirect =  None, form_data = None):
	if redirect:
		print 'Status: 303 See Other\r\n',
		print 'Location: %s\r\n' % redirect,
	print 'Content-type: text/html; charset=utf-8\r\n',
	print '\r\n',
	template = Templates(templates_path, db, actyear)
	print template.get_main_header()
	for a in articles:
		print template.get_article_header(a)
		print a.to_html()
		print template.get_article_footer(a)
		if show_comments:
			render_comments(a, template, form_data)
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
		vars = a.to_vars()
		vars.update( {
			'url': full_url,
			'contents': a.to_html(),
		} )
		print """
  <entry>
    <title>%(arttitle)s</title>
    <author><name>%(author)s</name></author>
    <link href="%(url)s/post/%(uuid)s" />
    <id>%(url)s/post/%(uuid)s</id>
    <summary>%(arttitle)s</summary>
    <published>%(ciso)sZ</published>
    <updated>%(uiso)sZ</updated>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml"><p>
%(contents)s
      </p></div>
    </content>
  </entry>
		""" % vars
	print "</feed>"


def render_style():
	print 'Content-type: text/css\r\n\r\n',
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
	comment = False

	if os.environ.has_key('PATH_INFO'):
		path_info = os.environ['PATH_INFO']
		style = path_info == '/style'
		atom = path_info == '/atom'
		tag = path_info.startswith('/tag/')
		post = path_info.startswith('/post/')
		artlist = path_info.startswith('/list')
		comment = path_info.startswith('/comment/') and enable_comments
		if not style and not atom and not post and not tag \
				and not comment and not artlist:
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
		elif comment:
			uuid = path_info.replace('/comment/', '')
			uuid = uuid.replace('#comment', '')
			uuid = uuid.replace('/', '')
			author = form.getfirst('comformauthor', '')
			link = form.getfirst('comformlink', '')
			captcha = form.getfirst('comformcaptcha', '')
			body = form.getfirst('comformbody', '')

	db = ArticleDB(os.path.join(data_path, 'db'))
	if atom:
		articles = db.get_articles(tags = tags)
		articles.sort(reverse = True)
		render_atom(articles[:10])
	elif style:
		render_style()
	elif post:
		render_html( [db.get_article(uuid)], db, year, enable_comments )
	elif artlist:
		articles = db.get_articles()
		articles.sort(cmp = Article.title_cmp)
		render_artlist(articles, db)
	elif comment:
		form_data = CommentFormData(author.strip().replace('\n', ' '),
				link.strip().replace('\n', ' '), captcha, body)
		article = db.get_article(uuid)
		captcha = Captcha(article)
		redirect = False
		valid = True
		if not form_data.author:
			form_data.author_error = 'please, enter your name'
			valid = False
		if form_data.link:
			link = valid_link(form_data.link)
			if link:
				form_data.link = link
			else:
				form_data.link_error = 'please, enter a ' \
						'valid link'
				valid = False
		if not captcha.validate(form_data):
			form_data.captcha_error = captcha.help
			valid = False
		if not form_data.body:
			form_data.body_error = 'please, write a comment'
			valid = False
		else:
			error = validate_rst(form_data.body)
			if error is not None:
				(line, desc, ctx) = error
				form_data.body_error = 'error at line %d: %s' \
						% (line, desc)
				valid = False
		if valid:
			c = article.add_comment(form_data.author,
					form_data.body, form_data.link)
			c.save()
			cdb = CommentDB(article)
			cdb.comments = article.comments
			cdb.save()
			redirect = blog_url + '/post/' + uuid + '#comment-' \
					+ str(c.number)
		render_html( [article], db, year, enable_comments, redirect,
				form_data )
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
	art_path = art_path[len(data_path)+1:]

	db_filename = os.path.join(data_path, 'db')
	if not os.path.isfile(db_filename):
		open(db_filename, 'w').write('')
	db = ArticleDB(db_filename)

	if cmd == 'add':
		article = Article(art_path, datetime.datetime.now(),
					datetime.datetime.now())
		for a in db.articles:
			if a == article:
				print 'Error: article already exists'
				return 1
		db.articles.append(article)
		db.save()
		if enable_comments:
			comment_dir = os.path.join(comments_path, article.uuid)
			try:
				os.mkdir(comment_dir, 0775)
			except OSError, e:
				if e.errno != errno.EEXIST:
					print "Error: can't create comments " \
						"directory %s (%s)" \
							% (comment_dir, e)
				# otherwise is probably a removed and re-added
				# article
	elif cmd == 'rm':
		article = Article(art_path)
		for a in db.articles:
			if a == article:
				break
		else:
			print "Error: no such article"
			return 1
		if enable_comments:
			r = raw_input('Remove comments [y/N]? ')
		db.articles.remove(a)
		db.save()
		if enable_comments and r.lower() == 'y':
			shutil.rmtree(os.path.join(comments_path, a.uuid))
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



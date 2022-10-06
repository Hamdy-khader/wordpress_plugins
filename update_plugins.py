#!/usr/bin/env python

'''
This script helps automatically keep your wordpress themes and
plugins up-to-date. It requires that you install themes and plugins
using subversion from the approriate wordpress.org repo. When run,
this script checks the upstream repo for the latest svn tag, and
switches your checked out repo to the latest tag.

Set your wordpress install dir path and wordpress user at the top
of the script. When finished updating, this script chowns your
repo to the approriate wordpress_user.

We only update themes and plugins that are hosted by wordpress.org
In order to start, you need to check out your plugins using svn.

For example:
#svn co http://plugins.svn.wordpress.org/wp-syntax/tags/0.9.12 /var/www/wordpress/wp-content/plugins/wp-syntax

For some reason, themes hosted on wordpress.org don't use the
standard svn directory layout, so you have to check them out like so:
#svn co http://themes.svn.wordpress.org/p2/1.3.2 /var/www/wordpress/wp-content/themes/p2
'''


import os
import re
import sys
import glob
import commands
import lxml.etree as ET
from distutils.version import LooseVersion
import shutil

import requests

wordpress_install_dir = '/home/lamp/wordpress'
updated = False
#wordpress_install_dir = '.'
#wordpress_user = 'www-data'

#run_cmd()
#_______________________________________________________________________________
def run_cmd(cmd):
    status, output = commands.getstatusoutput(cmd)
    if 0 != status:
        print "  > cmd %s failed with status code %d" % (cmd, status)
        print "  > %s" % output

    return output

#get_svn_info()
#_______________________________________________________________________________
def get_svn_info(tree):
    failure = [None, None, None]
    if not os.path.isdir(tree):
        print '  not a directory'
        return failure

    if not os.path.isdir(tree+'/.svn'):
        print '  not a svn tree'
        return failure

    info = run_cmd('svn info --xml ' + commands.mkarg(tree))

    infotree = ET.fromstring(info)

    entry = infotree.find('entry')
    if entry is None:
        print '  no svn entry found'
        return failure

    url = entry.find('url')
    if url is None:
        print '  no svn url found'
        return failure

    print '  url:  ', url.text

    usesTag = True
    if url.text.startswith('http://themes.svn.wordpress.org') or url.text.startswith('https://themes.svn.wordpress.org'):
        m = re.match('(http[s]?://themes.svn.wordpress.org/(?:\S+?))/(\S+)', url.text)
    elif url.text.startswith('http://plugins.svn.wordpress.org') or url.text.startswith('https://plugins.svn.wordpress.org'):
        m = re.match('(http[s]?://plugins.svn.wordpress.org/(?:\S+?))/tags/(\S+)', url.text)
        if m is None:
            m = re.match('(http[s]?://plugins.svn.wordpress.org/(?:\S+?))/trunk', url.text)
            usesTag = False

    else:
        print '  not a wordpress.org plugin/theme repo, skipping'
        return failure

    if m is None:
        print '  repo url does not match pattern'
        return failure
    if usesTag and m.group(2) is None:
        print '  could not parse tag'
        return failure

    repo_url = m.group(1)

    if not usesTag:
        trunk_url = repo_url + '/trunk'
        cmd = '  svn update ' + commands.mkarg(tree)
        print cmd
        run_cmd(cmd)
        current_tag = "trunk"
    else :
        current_tag = m.group(2)

    commit = entry.find('commit')
    if commit is None:
        print '  no commit tag found'
        return failure
    current_rev = int(commit.attrib['revision'])

    return repo_url, current_tag, current_rev


#get_newest_svn_tag()
#_______________________________________________________________________________
def get_newest_svn_tag(repo_url):
    print '  getting svn tags for repo'
    failure = [None, None]
    newest_tag = '0.0'
    newest_rev = 0

    tag_url = repo_url
    #print '  ', tag_url
    if repo_url.startswith('http://plugins.svn.wordpress.org') or repo_url.startswith('https://plugins.svn.wordpress.org'):
        tag_url += '/tags'
        #print '  ', tag_url

    list = run_cmd('svn list --xml ' + commands.mkarg(tag_url))

    tree = ET.fromstring(list)
    entries = tree.findall('list/entry')
    if 0 == len(entries):
        print '  could not get tags for repo'
        return failure

    for entry in entries:
        commit = entry.find('commit')
        rev = int(commit.attrib['revision'])
        name = entry.find('name')
        if name is None:
            print '  no tag name found'
            return failure

        tag = name.text

        m = re.match('^[\.\d]+$', tag )
        if not ( m is None ) and LooseVersion(tag) > LooseVersion(newest_tag):
            newest_rev = rev
            newest_tag = tag

    print '  found newest_rev = %d, newest_tag = %s' % (newest_rev, newest_tag)
    return newest_rev, newest_tag


#switch_to_svn_tag()
#_______________________________________________________________________________
def switch_to_svn_tag(tree, repo_url, tag):
    global updated
    print '  switching repo to tag %s' % tag

    if repo_url.startswith('http://themes.svn.wordpress.org') or repo_url.startswith('https://themes.svn.wordpress.org'):
        tag_url = repo_url+'/'+tag
    else:
        tag_url = repo_url+'/tags/'+tag

    cmd = 'svn switch --ignore-ancestry ' + commands.mkarg(tag_url) + commands.mkarg(tree)
    status, output = commands.getstatusoutput(cmd)
    if status != 0:
        print "  > cmd %s failed with status code %d" % (cmd, status)
        raise Exception(output)
    updated = True

def switch_to_svn_trunk(tree, repo_url):
    global updated
    trunk_url = repo_url + "/trunk"
    print '  switching repo to trunk %s' % trunk_url

    cmd = 'svn switch --ignore-ancestry ' + commands.mkarg(trunk_url) + commands.mkarg(tree)
    run_cmd(cmd)
    updated = True

#    cmd = 'chown -R' + commands.mkarg(wordpress_user) + commands.mkarg(tree)
#    run_cmd(cmd)

#update_svn_trees()

tmpDir = os.path.expanduser("~") + "/tmpsvn"

def get_readme_version(tree, repo_url):
    if(os.path.exists(tmpDir)):
        shutil.rmtree(tmpDir)
    os.mkdir(tmpDir)

    cmd = 'svn co --depth files ' + commands.mkarg(repo_url) + "/trunk" + commands.mkarg(tmpDir)
    run_cmd(cmd)

    readmefile = '%s/readme.txt' % tmpDir

    if os.path.isfile(readmefile):
        f = open(readmefile, 'r')
        m = re.search("Stable tag: ([\w.]+)", f.read())
        if (m) :
            return m.group(1)


def get_latest_theme_version(repo_url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.request("GET", repo_url, headers=headers)
    if response.status_code == 200:
        et = ET.HTML(response.text)
        try:
            ver = et[1][1][-1][0].text.replace("/", "")
            ver = ver.strip()
            print 'Latest version: %s' % ver
            return ver
        except:
            pass
    else:
        print "URL error: %s, %s" % (response.status_code, repo_url)

#____________________________________________________________________________
def update_svn_trees(trees):
    '''
    updates svn trees to the latest tag
    skips paths that aren't svn trees

    switch to comparing SVN tag names using LooseVersion, instead of comparing
    SVN revision numbers, since sometimes older tags have higher rev numbers.
    '''

    for tree in trees:

        print 'checking ' + tree

        repo_url, current_tag, current_rev = get_svn_info(tree)
        if current_tag is None:
            continue;

        print '  current tag is %s (revision %d)' % (current_tag, current_rev)
        #print '  repo url is %s' % repo_url

        if "themes.svn.wordpress.org" in repo_url:
            newest_tag = get_latest_theme_version(repo_url)
            if newest_tag is None:
                print 'Can not get latest tag, skip'
                continue
            if LooseVersion(newest_tag) != LooseVersion(current_tag):
                print 'New version found!, %s, %s' % (repo_url, newest_tag)
                try:
                    switch_to_svn_tag(tree, repo_url, newest_tag)
                except Exception as e:
                    print(e)
        else:
            newest_tag = get_readme_version(tree, repo_url)
            if newest_tag is None:
                print '  stable tag not found from readme! falling back to trunk ...'
                newest_tag = "trunk"
            else :
                print '  stable tag found from readme.txt: ', newest_tag

            if LooseVersion(newest_tag) != LooseVersion(current_tag):
                if (newest_tag == "trunk") :
                    switch_to_svn_trunk(tree, repo_url)
                else:
                    try:
                        switch_to_svn_tag(tree, repo_url, newest_tag)
                    except Exception as e:
                        print(e)
                        print '  failed to switch to tag %s, falling back to trunk ... ' % newest_tag
                        if (current_tag != "trunk") :
                            switch_to_svn_trunk(tree, repo_url)



# main()
#_______________________________________________________________________________

uid = os.getuid()
if 0 != uid:
   print 'This script must be run as root!'
   sys.exit(-1)

plugins = glob.glob('%s/plugins/*' % wordpress_install_dir)
update_svn_trees(plugins)

themes = glob.glob('%s/themes/*' % wordpress_install_dir)
update_svn_trees(themes)
if updated:
    print " reload php7.3-fpm"
    run_cmd("service php7.3-fpm reload")
    run_cmd("service php8.0-fpm reload")

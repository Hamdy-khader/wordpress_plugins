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

wordpress_install_dir = '/home/lamp/wordpress'
#wordpress_user = 'www-data'

#run_cmd()
#_______________________________________________________________________________
def run_cmd(cmd):
    status, output = commands.getstatusoutput(cmd)
    if 0 != status:
        print "cmd %s failed with status code %d" % (cmd, status)
        sys.exit(-1)

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

    print '  ', url.text

    usesTag = True
    if url.text.startswith('http://themes.svn.wordpress.org'):
        m = re.match('(http://themes.svn.wordpress.org/(?:\S+?))/(\S+)', url.text)
    elif url.text.startswith('http://plugins.svn.wordpress.org'):
        m = re.match('(http://plugins.svn.wordpress.org/(?:\S+?))/tags/(\S+)', url.text)
        if m is None:
            m = re.match('(http://plugins.svn.wordpress.org/(?:\S+?))/trunk', url.text)
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
        trunk_url = repo_url+'/trunk'
        cmd = 'svn update ' + commands.mkarg(tree)
        print cmd
        run_cmd(cmd)
        return None, None, None

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
    if repo_url.startswith('http://plugins.svn.wordpress.org'):
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
    print '  switching repo to tag %s' % tag

    if repo_url.startswith('http://themes.svn.wordpress.org'):
        tag_url = repo_url+'/'+tag
    else:
        tag_url = repo_url+'/tags/'+tag

    cmd = 'svn switch --ignore-ancestry ' + commands.mkarg(tag_url) + commands.mkarg(tree)
    run_cmd(cmd)

#    cmd = 'chown -R' + commands.mkarg(wordpress_user) + commands.mkarg(tree)
#    run_cmd(cmd)

#update_svn_trees()
#_______________________________________________________________________________
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
            continue

        print '  current tag is %s (revision %d)' % (current_tag, current_rev)
        print '  repo url is %s' % repo_url

        newest_rev, newest_tag = get_newest_svn_tag(repo_url)
        if newest_tag is None:
            print '  getting newest tag failed!'
            continue
        print '  newest tag is %s (revision %d)' % (newest_tag, newest_rev)

        if LooseVersion(newest_tag) > LooseVersion(current_tag):
            switch_to_svn_tag(tree, repo_url, newest_tag)

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

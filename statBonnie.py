#!/usr/bin/env python3

import sys
import os
import re
import math
import logging
import argparse
from xml.dom.minidom import parseString
from namedtree import NamedTree, NamedTreeGroup, OP_KIND_LEAF, OP_KIND_DIR


log = logging.getLogger()

IO_PATTERN = ('putc', 'write', 'read_wirte', 'getc', 'read')
IO_MEASURE = ('kB/s', '%CPU')
PR_FORMAT = {'kB/s': '{0:%ds}\t{1:>%d.0f}\t{2:>%d.0f}\t{3:>%d.2f}',
             '%CPU': '{0:%ds}\t{1:>%d.2f}\t{2:>%d.2f}\t{3:>%d.2f}%%'}

class PaintUnit:
    def __init__(self, obj, name = None):
        self.obj = obj

    def get_width(self):
        return len(str(self.obj))

    def __str__(self):
        return str(self.obj)

PST_NULL, PST_ERROR, PST_START, PST_END, PST_ONERUN, PST_ONETABLE = range(6)
class BonnieSample(NamedTree):

    def __init__(self, filename, name = None):
        self.filename = filename
        if not name:
            super().__init__(filename)
        else:
            super().__init__(name)

        tree = {}
        for iopt in IO_PATTERN:
            tree[iopt] = {}
        
        self.tree = tree

        self.fd = None
        self.parse_ST = PST_NULL

    def _pas_TD(self, tds):
        ''' No error check '''
        #tds[0].firstChild.data #hostname
        # condition
        fr = re.match(r'(\d+)\s*\*\s*(\d+)', tds[1].firstChild.data)
        fsize = int(fr.group(1))
        iocount = int(fr.group(2))

        # objects and result
        i = 2
        for ptn in IO_PATTERN:
            result_tree = {}
            result_tree[IO_MEASURE[0]] = int(tds[i].firstChild.data)
            result_tree[IO_MEASURE[1]] = float(tds[i + 1].firstChild.data)
            ptn_tree = self.tree[ptn]
            if fsize in ptn_tree:
                fsize_tree = ptn_tree[fsize]
            else:
                fsize_tree = {}
                ptn_tree[fsize] = fsize_tree
            if iocount in fsize_tree:
                iocount_tree = fsize_tree[iocount]
                log.warning('duplicate bonnie data')
            else:
                iocount_tree = result_tree
                fsize_tree[iocount] = iocount_tree

    def _pas_TR(self):
        for line in self.fd:
            if re.match(r'^<TR><TD>', line):
                self.parse_ST == PST_ONETABLE
                try:
                    domt = parseString(line)
                    tr = domt.firstChild
                    nt = self._pas_TD(tr.childNodes)
                except Exception as a:
                    raise a
                return
        self.parse_ST = PST_ERROR

    def _pas_RUN(self):
        for line in self.fd:
            if re.match(r'^Needing\s*(\d*)\s*MB', line):
                self.parse_ST = PST_ONERUN
                return
        self.parse_ST = PST_END

    def parse(self):
        if self.parse_ST == PST_NULL:
            self.fd = open(self.filename)
            self.parse_ST = PST_START

        if self.parse_ST == PST_START:
            self.parse_ST = PST_ONETABLE

        while self.parse_ST != PST_END:
            if self.parse_ST == PST_ONETABLE:
                self._pas_RUN()
            if self.parse_ST == PST_ONERUN:
                self._pas_TR()
            if self.parse_ST == PST_ERROR:
                self.parse_ST = PST_END

def get_samples_in_dir(dirname):
    pattern = re.compile('bonnie-directIO-(\d{4}-\d{2}-\d{2})-(\d{2})-(\d{2})-(\d{2})')
    db = []
    for name in os.listdir(dirname):
        r = pattern.match(name)
        if r:
            sample_name = "%sT%s:%s:%s" % (r.group(1), r.group(2),
                                           r.group(3), r.group(4))
            filename = dirname + '/' + name + '/' + 'bonnie-directIO'
            db.append(BonnieSample(filename, sample_name))
    return db

class BonnieSampleGroup(NamedTreeGroup):
    def __init__(self, *T_list):
        super().__init__(*T_list)
        for k in IO_MEASURE:
            self.width[k] = [0, 0, 6]
        self.width['%CPU'] = [7, 7, 6]

    @NamedTreeGroup.group_noreturn(kind = OP_KIND_LEAF)
    def accum_width(path, k, t_list, self):
        l = 0
        for n in path:
            l += len(str(n)) + 1
        self.width['path'] = max(self.width['path'], l)

        # ignore the ratio part
        if k not in IO_MEASURE:
            log.warning('unknow IO_MEASURE %s' % k)
            return

        if k == 'kB/s':
            t_list = t_list[0:2]
            width_k = (self.width[k][0], self.width[k][1])
            leaf_list = list(map(lambda t:t[k], t_list))
            self.width[k][0], self.width[k][1] = list(map(lambda leaf, width:max(len(str(leaf)), len(str(width))), leaf_list, width_k))

    def pnt_result(self):
        self.accum_width()
        tplt = {}
        tplt['row_name'] = '{0:%ds}' % self.width['path']
        w = self.width['kB/s']
        tplt['kB/s'] = '\t{0:>%d.0f}  {1:>%d.0f}  {2:>%d.2f}%%' % (w[0], w[1], w[2])
        w = self.width['%CPU']
        tplt['%CPU'] = '\t{0:>%d.2f}  {1:>%d.2f}  {2:>%d.2f}%%' % (w[0], w[1], w[2])
        self.tplt = tplt
        self.pnt_header()
        self.pnt_mono()

    def pnt_header(self):
        name = (str(self.T_list[0].name), str(self.T_list[1].name), '')
        name_len = list(map(len, name))
        header_tplt = {}
        sys.stdout.write(self.tplt['row_name'].format('bonnie'))
        for k in IO_MEASURE:
            w = self.width[k]
            if w[0] < name_len[0]:
                w[0] = name_len[0]
            if w[1] < name_len[1]:
                w[1] = name_len[1]
            header_tplt[k] = '\t{0:>%ds}  {1:>%ds}  {2:>%d.2s}' % (w[0], w[1], w[2])
            
            sys.stdout.write(header_tplt[k].format(*name))

        print()

    @NamedTreeGroup.group_noreturn(kind = OP_KIND_DIR)
    def pnt_mono(path, t_spec, t_list, self):
        row_name = ' '.join(list(map(lambda d:str(d), path)))
        sys.stdout.write(self.tplt['row_name'].format(row_name))
        kb_s = list(map(lambda t:t['kB/s'], t_list))
        sys.stdout.write(self.tplt['kB/s'].format(*kb_s))
        cpu_p = list(map(lambda t:t['%CPU'], t_list))
        sys.stdout.write(self.tplt['%CPU'].format(*cpu_p))
        if cpu_p[2] < -0.15:
            print('\t***')
        else:
            print()

def main():
    cmdlineparser = argparse.ArgumentParser(description = 'BonnieSample Parser', prog = 'BonnieSample')
    cmdlineparser.add_argument('db', nargs='+')

    ns = cmdlineparser.parse_args(sys.argv[1:])
    if len(ns.db) != 2:
        print('Usages')

    db0 = get_samples_in_dir(ns.db[0])
    db1 = get_samples_in_dir(ns.db[1])

    for t in db0:
        t.parse()

    for t in db1:
        t.parse()

    #print(type(NamedTree.operator.average))

    #average0 = NamedTree.operator.average(*db0)
    #average0.set_name(os.path.basename(ns.db[0]))
    group0 = NamedTreeGroup(*db0)
    average0 = group0.average()
    average0.name = os.path.basename(ns.db[0])
    #average1 = NamedTree.operator.average(*db1)
    #average1.set_name(os.path.basename(ns.db[1]))
    group1 = NamedTreeGroup(*db1)
    average1 = group1.average()
    average1.name = os.path.basename(ns.db[1])

    diff_ratio = NamedTree.Operator.diff_ratio(average0, average1)


    #union = NamedTree.operator.union(average0, average1, diff_ratio)
    #NamedTree.painter.single(union)

    ngroup = BonnieSampleGroup(average0, average1, diff_ratio)
    #ngroup.painter = NamedTreePainter(info)

    ngroup.pnt_result()

if __name__ == '__main__':
    main()

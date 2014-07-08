import sys
from collections import OrderedDict
import logging

__all__ = ['NamedTree', 'NamedTreeGroup', 'OP_KIND_LEAF', 'OP_KIND_DIR']

log = logging.getLogger()

def _get_key_set(t_list):
    key_uset = set()
    for l in t_list:
        key_uset |= l.keys()

    key_iset = key_uset
    for l in t_list:
        key_iset &= l.keys()

    key_dset = key_uset - key_iset
    return key_uset, key_iset, key_dset

(CHK_OK, CHK_NO_ITEM, CHK_NOT_DICT) = list(range(0,3))
def _check_key(k, t_list, info, error):
    iter_t = iter(t_list)
    iter_i = iter(info)
    _list = []
    while True:
        try:
            t = next(iter_t)
            info = next(iter_i)
            if k not in t:
                _list.append(info)
        except StopIteration:
            break

    if len(_list) == 0:
        # Do not touch error
        return True
    else:
        error[0], error[1] = (CHK_NO_ITEM, _list)
        return False

def _check_dir(k, t_list, info, error):
    iter_t = iter(t_list)
    iter_i = iter(info)
    _list = []
    while True:
        try:
            t = next(iter_t)
            info = next(iter_i)
            if not isinstance(t[k], dict):
                _list.append(info)
        except StopIteration:
            break

    if len(_list) == 0:
        # Do not touch error
        return True
    else:
        error[0], error[1] = (CHK_NOT_DICT, _list)
        return False

def _check_file(k, t_list, info, error):
    iter_t = iter(t_list)
    iter_i = iter(info)
    _list = []
    while True:
        try:
            t = next(iter_t)
            info = next(iter_i)
            if isinstance(t[k], dict):
                _list.append(info)
        except StopIteration:
            break

    if len(_list) == 0:
        # Do not touch error
        return True
    else:
        error[0], error[1] = (CHK_NOT_DICT, _list)
        return False



def named_tree_get_common(t_list, info):
    ''' Get the common structure of a list of named_tree
    info should be iteratable and each one is for each tree
    each info should have the name property for debug'''
    stack = []
    path = []
    error = [CHK_OK, None]

    key_uset, key_iset, key_dset = _get_key_set(t_list)
    key_uset = sorted(key_uset)
    root_node = OrderedDict()
    for e in key_uset:
        root_node[e] = None
    t_spec = root_node
    iter_iset = iter(key_iset)

    while True:
        try:
            k = next(iter_iset)
        except StopIteration:
            if len(stack) == 0:
                break
            else:
                si = stack.pop()
                (t_list, t_spec, iter_iset) = si
                path.pop()
        else:
            if _check_dir(k, t_list, info, error):
                si = (t_list, t_spec, iter_iset)
                stack.append(si)
                path.append(k)
                t_list = list(map(lambda d:d[k], t_list))
                key_uset, key_iset, key_dset = _get_key_set(t_list)
                key_uset = sorted(key_uset)
                new_node = OrderedDict()
                for e in key_uset:
                    new_node[e] = None
                t_spec[k] = new_node
                t_spec = new_node
                iter_iset = iter(key_iset)
            elif _check_file(k, t_list, info, error):
                log.debug('Node %s of Tree is a value')
            else:
                log.warning('unmatched data type found')
                for info in error[1]:
                    log.warning('%s of %s is a dict' % ('/' + '/'.join(path)+'/'+k, info.name))
                for info in info:
                    if info not in error[1]:
                        log.warning('%s of %s is NOT a dict' % ('/' + '/'.join(path)+'/'+k, info.name))
    return root_node

(OP_KIND_LEAF, OP_KIND_DIR) = list(range(0,2))
def named_tree_travel(op, t_spec, t_list, info, kind = OP_KIND_LEAF):
    ''' A depth first tree travel implmentation with two variants.
    OP_KIND_LEAF means op operate on the leaf node of the tree.
    OP_KIND_DIR means op operate on all the leaves with a common parent.
    info should be iteratable and each one is for each tree
    each info should have the name property for debug'''

    stack = []
    path = []
    error = [CHK_OK, None]

    iter_spec = iter(t_spec)
    root_node = {}
    t_result = root_node

    while True:
        try:
            k = next(iter_spec)
        except StopIteration:
            if len(stack) == 0:
                break
            else:
                si = stack.pop()
                (t_list, t_spec, iter_spec, t_result) = si
                path.pop()
        else:
            if not _check_key(k, t_list, info, error):
                for info in error[1]:
                    log.warning('%s has no data at %s' % (info.name, '/'+'/'.join(path[1:])+'/'+k))
            elif isinstance(t_spec[k], dict):
                if _check_dir(k, t_list, info, error):
                    si = (t_list, t_spec, iter_spec, t_result)
                    stack.append(si)
                    path.append(k)
                    t_list = list(map(lambda d:d[k], t_list))
                    t_spec = t_spec[k]
                    iter_spec = iter(t_spec)
                    t_result[k] = {}
                    t_result = t_result[k]
                else:
                    for info in error[1]:
                        message += '%s of %s is NOT a dict' % ('/'+'/'.join(path)+'/'+k, info.name) + '\n'
                    raise TypeError(message)
            else:
                if kind == OP_KIND_LEAF:
                    t_result[k] = op(path, k, t_list, info)
                elif kind == OP_KIND_DIR:
                    tmp = op(path, t_spec, t_list, info)
                    k = path.pop()
                    si = stack.pop()
                    (t_list, t_spec, iter_spec, t_result) = si
                    t_result[k] = tmp
                else:
                    log.warning('UNKNOWN kind of operation')
    return root_node

class NamedTree:
    ''' Could be used as a info for a named tree  '''
    #TODO change 'vector' to 'list'
    @classmethod
    def extract_spec(cls, *T_list):
        for T in T_list:
            if T.spec:
                return T.spec
        t_list = list(map(lambda T:T.get_tree(), T_list))
        t_spec = named_tree_get_common(t_list, T_list)
        return t_spec

    def __init__(self, name, tree = None):
        self.name = name
        self.tree = tree
        self.spec = None

    def set_name(self, name):
        self.name = name

    def _get_branch(self, path):
        ''' (dir1, dir2, dir3) '''
        if not self.tree:
            return {}
        node = self.tree
        for name in path:
            node=node[name]
        return node

    def get_branch(self, path):
        t = self._get_dir(path)
        name = '/'.join(path)
        return NamedTree(name, t)

    def set_branch(self, path, dir_v):
        pass

    def get_file(self, path):
        pass

    def set_file(self, path, file_v):
        pass

    def get_tree(self):
        return self.tree

    def set_tree(self, tree):
        self.tree = tree

# a decorator extract a named tree from a NamedTree
def operator(prefix, kind = OP_KIND_LEAF):
    def real(func):
        def wrapper(*T_list, info = None):
            t_spec = NamedTree.extract_spec(*T_list)
            t_list = list(map(lambda T:T.get_tree(), T_list))
            if not info:
                info = T_list
            r_tree = named_tree_travel(func, t_spec, t_list, info, kind = kind)
            t_names = list(map(lambda T:T.name, info))
            R_tree = NamedTree('%s %s' % (prefix, ' '.join(t_names)))
            R_tree.set_tree(r_tree)
            return R_tree
        return wrapper
    return real

# a decorator like operator without a return
def operator_noreturn(kind = OP_KIND_LEAF):
    def real(func):
        def wrapper(*vector, info = None):
            if not info:
                log.error('No PainterInfo Provided')
                return
            t_spec = NamedTree.extract_spec(*vector)
            t_list = list(map(lambda T:T.get_tree(), vector))
            named_tree_travel(func, t_spec, t_list, info, kind = kind)
        return wrapper
    return real


class Operator:
    '''The Namespace for Operators of NamedTree
    Some of them have only two operands, so they can be implemented
    as a special math method of NamedTree. Some ones have more than two operands.'''

    # math method
    #sum(*vector)
    @staticmethod
    @operator('the sum of')
    def sum(path, k, t_list, info):
        return sum(map(lambda t: t[k], t_list))

    @staticmethod
    @operator('the substract of')
    def substract(T1, T2):
        raise NotImplementedError()

    @staticmethod
    @operator('the multiply of')
    def multiply(*vector):
        raise NotImplementedError()

    @staticmethod
    @operator('the divide of')
    def divide(T1, T2):
        raise NotImplementedError()

    # average(*vector)
    @staticmethod
    @operator('the average of')
    def average(path, k, t_list, info):
        return sum(map(lambda t: t[k], t_list)) / len(t_list)

    # diff_ratio(T1, T2):
    @staticmethod
    @operator('the diff ratio of')
    def diff_ratio(path, k, t_list, info):
        diff = t_list[1][k] - t_list[0][k]
        ratio = diff / t_list[0][k]
        return ratio

    # union(*vector)
    @staticmethod
    @operator('the union list of')
    def union(path, k, t_list, info):
        return list(map(lambda t: t[k], t_list))

    @staticmethod
    def branch(path, *vector):
        error = []
        nv = []
        for T in vector:
            try:
                nT = T.get_dir(path)
                nv.append(nT)
            except KeyError as kerror:
                error.append((T, kerror))

        if len(error) != 0:
            raise keyError(error)
        else:
            return nv

    # painting methods
    @staticmethod
    @operator_noreturn(kind = OP_KIND_LEAF)
    def pnt_default(path, k, t_list, info):
        iter_t = iter(t_list)
        iter_i = iter(info)
        str_path = list(map(lambda e:str(e), path))
        prefix = '/'+'/'.join(str_path)+'/'+k
        i = 0
        prefix_space = str()
        while i < len(prefix):
            prefix_space += ' '
            i += 1

        t = next(iter_t)
        info = next(iter_i)
        print('%s of %s is %s' % (prefix, info.name, t[k]))

        while True:
            try:
                t = next(iter_t)
                info = next(iter_i)
                print('%s    %s is %s' % (prefix_space, info.name, t[k]))
            except StopIteration:
                break

    # spec(T_spec)
    @staticmethod
    @operator_noreturn(kind = OP_KIND_LEAF)
    def pnt_spec(path, k, t_list, info):
        print('%s' % ('/' + '/'.join(path)+'/'+k))

NamedTree.Operator = Operator
NamedTree.operator = operator
NamedTree.operator_noreturn = operator_noreturn

# a decorator for NamedTreeGroup
# some operations need to be done together to finish one job.
def group_noreturn(kind = OP_KIND_LEAF):
    def real(func):
        def wrapper(group):
            T_list = group.T_list
            t_spec = NamedTree.extract_spec(*T_list)
            t_list = list(map(lambda T:T.get_tree(), T_list))
            named_tree_travel(func, t_spec, t_list, group, kind = kind)
        return wrapper
    return real

class NamedTreeGroup:
    group_noreturn = group_noreturn

    def __init__(self, *T_list):
        self.T_list = T_list
        self.t_spec = NamedTree.extract_spec(*T_list)
        for T in T_list:
            T.spec = self.t_spec
        self.name = None
        self.width = {'path':0}
        self.template = {}

    def __iter__(self):
        return iter(self.T_list)

    def __getattr__(self, name):
        if hasattr(Operator, name):
            op = getattr(Operator, name)
            return lambda : op(*self.T_list, info = self)
        else:
            return AttributeError()
    
    @group_noreturn(kind = OP_KIND_LEAF)
    def accum_width(path, k, t_list, self):
        l = 0
        for n in path:
            l += len(str(n)) + 1
        self.width['path'] = max(self.width['path'], l)

        leaf_list = list(map(lambda t:t[k], t_list))
        if k not in self.width:
            self.width[k] = list(map(lambda leaf: len(str(leaf)), leaf_list))
        else:
            width_k = self.width[k]
            self.width[k] = list(map(lambda leaf, width:max(len(str(leaf)), len(str(width))), leaf_list, width_k))

    @group_noreturn(kind = OP_KIND_DIR)
    def pnt_mono(path, t_spec, t_list, self):
        sys.stdout.write('/'.join(list(map(lambda d:str(d), path))))
        for k in t_spec:
            for tree in t_list:
                sys.stdout.write('\t')
                sys.stdout.write(str(tree[k]))
        print()


if __name__ == '__main__':
    ntree1 = {
        'L1K0':{
            'L2K0':{
                'L3K0':{
                    'L4K0':1, 'L4K1':2,'L4K2':3
                },
                'L3K1':{
                    'L4K0':0.4, 'L4K1':0.5, 'L4K2':0.6
                }
            },
            'L2K1':{
                'L3K0':{
                    'L4K0':2.1, 'L4K1':2.2, 'L4K2':2.3
                },
                'L3K1':{
                    'L4K0':3, 'L4K1':4, 'L4K2':5
                }
            },
        }
    }
    T1 = NamedTree('T1')
    T1.set_tree(ntree1)

    ntree2 = {
        'L1K0':{
            'L2K0':{
                'L3K0':{
                    'L4K0':1.1, 'L4K1':2.1,'L4K2':3.1
                },
                'L3K1':{
                    'L4K0':0.41, 'L4K1':0.51, 'L4K2':0.61
                }
            },
            'L2K1':{
                'L3K0':{
                    'L4K0':2.12, 'L4K1':2.22, 'L4K2':2.32
                },
                'L3K1':{
                    'L4K0':6, 'L4K1':7, 'L4K2':8
                }
            },
        }
    }
    T2 = NamedTree('T2')
    T2.set_tree(ntree2)

    ntree3 = {
        'L1K0':{
            'L2K0':{
                'L3K0':{
                    'L4K0':1.1, 'L4K1':2.1,'L4K2':3.1
                },
                'L3K1':101 # not a dict
            },
            'L2K1':{
                'L3K0':{
                    'L4K0':2.12, 'L4K1':2.22, 'L4K2':2.32
                },
                'L3K1':{
                    'L4K0':6, 'L4K1':7, 'L4K2':8
                }
            },
        }
    }
    T3 = NamedTree('T3')
    T3.set_tree(ntree3)

    ntree4 = {
        'L1K0':{
            'L2K0':{
                'L3K0':{
                    'L4K0':1, 'L4K1':2,'L4K2':3
                },
            },
            'L2K1':{
                'L3K1':{
                    'L4K0':3, 'L4K1':4, 'L4K2':5
                }
            },
        }
    }
    T4 = NamedTree('T4')
    T4.set_tree(ntree4)

    # test_named_ntree_get_common
    print(ntree1)
    #spec = NamedTree.get_spec_tree(T1, T2)
    print(spec.name)
    NamedTreePainter.spec(spec)


    NamedTreePainter.default(T1, T2)

    average_T1_T2 = NamedTreeOperater.average(T1, T2)
    NamedTreePainter.default(average_T1_T2)

    sum_T1_T2 = NamedTreeOperater.sum(T1, T2)
    NamedTreePainter.default(sum_T1_T2)

    diff_ratio_T1_T2 = NamedTreeOperater.diff_ratio(T1, T2)
    NamedTreePainter.default(diff_ratio_T1_T2)

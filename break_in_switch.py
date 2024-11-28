import re, os
import pycparser # [https://stackoverflow.com/questions/11143095/parsing-c-code-using-python <- google:‘python parse c code’]

from pycparser import c_ast


class SwitchVisitor(c_ast.NodeVisitor):
    times_of_last_default_without_break = 0
    times_of_last_case_without_break = 0
    num_of_switches_with_case_without_break = 0
    total_num_of_switches = 0

    def visit_Switch(self, node):
        if node.coord.file.endswith('.h'):
            return

        assert type(node.stmt) == c_ast.Compound

        switch_with_case_without_break = False

        for case in node.stmt.block_items:
            assert type(case) in (c_ast.Case, c_ast.Default)
            if len(case.stmts):
                if type(case.stmts[-1]) in (c_ast.Break, c_ast.Continue, c_ast.Return, c_ast.Goto):
                    continue

                if type(case.stmts[-1]) == c_ast.Switch: # for `case CDROMPAUSE` in sbpcd.c
                    all_return = True
                    for sub_case in case.stmts[-1].stmt.block_items:
                        if len(sub_case.stmts) and type(sub_case.stmts[-1]) != c_ast.Return:
                            all_return = False
                            break
                    if all_return:
                        continue

                if type(case.stmts[0]) == c_ast.Compound and type(case.stmts[0].block_items[-1]) in (c_ast.Break, c_ast.Continue, c_ast.Return, c_ast.Goto): # for `case CDROMPLAYTRKIND: ... {...int track_idx;...return 0;}` in cdu31a.c
                    continue

                if case is node.stmt.block_items[-1]: # в последнем `case` можно не писать `break`, просто считаем количество таких случаев для статистики
                    if type(case) == c_ast.Default:
                        self.times_of_last_default_without_break += 1
                    else:
                        self.times_of_last_case_without_break += 1
                else:
                    print(case.coord)
                    switch_with_case_without_break = True

        if switch_with_case_without_break:
            self.num_of_switches_with_case_without_break += 1
        self.total_num_of_switches += 1

        self.generic_visit(node) # >[pycparser/_ast_gen.py]:‘The children of nodes for which a visit_XXX was defined will not be visited - if you need this, call generic_visit() on the node.’

if __name__ == "__main__":
    filename = 'all.c'

    if not os.path.exists(filename):
        all = open(filename, 'w')
        for root, dirs, files in os.walk('linux'):
            for name in files:
                if name.endswith('.c'):
                    if root == r'linux\drivers\net':     continue # fix error: dev.h: No such file or directory
                    if root == r'linux\zBoot':           continue # fix error: a.out.h: No such file or directory
                    if root == r'linux\drivers\FPU-emu': continue # avoid `#define regs` and `#define top` in FPU-emu/fpu_system.h
                    all.write(f'#include "{os.path.join(root, name)}"\n')
        all.close()

    ast = pycparser.parse_file(filename, use_cpp=True,
                     cpp_args=[
                         '-D__KERNEL__', # >[linux/Makefile]:‘CC =gcc -D__KERNEL__’
                         '-D__attribute__(x)=', # >[https://eli.thegreenplace.net/2015/on-parsing-c-type-declarations-and-fake-headers/ <- https://stackoverflow.com/questions/49128661/pycparser-parseerror <- google:‘pycparser suppress ParseError’]:‘note a GNU-specific __attribute__ pycparser doesn't support. No problem, let's just #define it away:...-D'__attribute__(x)='’
                         '-D__extension__(...)=0',
                         '-D__asm__(...)=',
                         '-D__volatile__(...)=', '-D__inline__=', '-Iutils/fake_libc_include', '-Ilinux/include',
                         '-Wno-endif-labels'])
    #stripped = re.sub(r'^#.+$', '\n', re.sub(r'/\*[\s\S]*?\*/', '', open(filename).read()), flags = re.MULTILINE)
    """
    stripped = open(filename).read()

    open(filename + '.s', 'w').write(stripped)
    ast = pycparser.CParser().parse(stripped, filename)
    """

    v = SwitchVisitor()
    v.visit(ast)

    print('Switches with case without break:', v.num_of_switches_with_case_without_break, '/', v.total_num_of_switches)
    print('Times of last case without break:', v.times_of_last_case_without_break)
    print('Times of last default without break:', v.times_of_last_default_without_break)

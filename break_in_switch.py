import re, os
import pycparser # [https://stackoverflow.com/questions/11143095/parsing-c-code-using-python <- google:‘python parse c code’]

from pycparser import c_ast


duffs_device_cases = [] # [https://en.wikipedia.org/wiki/Duff's_device <- http://compiler.su/prodolzhenie-tsikla-i-vykhod-iz-nego.php#55]

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

            class CaseVisitor(c_ast.NodeVisitor):
                def visit_Case(self, node):
                    duffs_device_cases.append(str(node.coord))
                    self.generic_visit(node)
                def visit_Switch(self, node):
                    pass
            CaseVisitor().generic_visit(case)

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

    if False: # process [https://github.com/mortdeus/legacy-cc <- http://compiler.su/prodolzhenie-tsikla-i-vykhod-iz-nego.php#62]
        def find_ending_curly_bracket(source, i):
            assert(source[i] == "{") # }
            nesting_level = 0
            while True:
                if i == len(source):
                    exit(1)
                ch = source[i]
                if ch == '{':
                    nesting_level += 1
                elif ch == '}':
                    nesting_level -= 1
                    if nesting_level == 0:
                        return i
                i += 1

        all = open(filename, 'w')
        all.write("void f() {\n")
        for root, dirs, files in os.walk('legacy-cc-master'):
            for name in files:
                if name.endswith('.c'):
                    source = open(os.path.join(root, name)).read()
                    source = source.replace('=<<', '<<=')
                    source = source.replace('goto const;', 'goto const_;').replace('const:', 'const_:')

                    # for found in re.finditer(R'\bswitch ?\(.+\) ?\{', source): # } # \
                    #     endi = find_ending_curly_bracket(source, found.end() - 1)  # - WORKS INCORRECTLY FOR NESTED SWITCHES
                    #     all.write(source[found.start():endi+1] + "\n")             # /

                    pattern = re.compile(R'\bswitch ?\(.+\) ?\{') # }
                    pos = 0
                    while True:
                        found = pattern.search(source, pos)
                        if found is None:
                            break
                        endi = find_ending_curly_bracket(source, found.end() - 1)
                        all.write(source[found.start():endi+1] + "\n")
                        pos = endi
        all.write("}\n")
        all.close()

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

    print(f"Duff's device cases [{len(duffs_device_cases)}]:")
    print("\n".join(duffs_device_cases))

import os

def generate_tree(startpath):
    output = []
    for root, dirs, files in os.walk(startpath):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.venv', '.idea', 'backup', 'scratch_git_clone']]
        
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * (level)
        output.append(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for f in sorted(files):
            if not f.endswith('.pyc') and not f.endswith('.pth') and not f.endswith('.pt'):
                output.append(f'{subindent}{f}')
    return '\n'.join(output)

if __name__ == '__main__':
    with open('project_structure.txt', 'w', encoding='utf-8') as f:
        f.write(generate_tree('.'))
    print("Project structure written to project_structure.txt")

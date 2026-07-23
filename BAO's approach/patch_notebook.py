import json

with open('Handwash_Train_Colab.ipynb', 'r', encoding='utf-8') as f:
    raw_data = f.read()

# Fix the garbage at the end
import re
raw_data = re.sub(r'\}\"\n<parameter name="toolAction".*', r'}', raw_data, flags=re.DOTALL)
# Make sure it ends with }
if raw_data.strip().endswith('}'):
    pass

nb = json.loads(raw_data)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'id' in cell['metadata']:
        cell_id = cell['metadata']['id']
        
        # Cell 2: Explore & Read Label
        if cell_id == 'cell_02_explore':
            source = "".join(cell['source'])
            source = source.replace("""label_df = None
for fname in bao_files:
    if 'label' in fname.lower():
        label_path = os.path.join(BAO_DIR, fname)
        print(f'Tìm thấy label file: {fname}')
        try:
            if fname.endswith('.xlsx') or fname.endswith('.xls'):
                label_df = pd.read_excel(label_path)
            elif fname.endswith('.csv'):
                label_df = pd.read_csv(label_path)
            else:
                # Thử đọc như text
                with open(label_path, 'r', encoding='utf-8', errors='ignore') as f_:
                    content = f_.read()
                print('Nội dung raw:')
                print(content)
                # Thử parse như CSV
                from io import StringIO
                label_df = pd.read_csv(StringIO(content))
        except Exception as e:
            print(f'Lỗi đọc label: {e}')
        break""", """label_df = None
# Tìm đệ quy để vào tận trong thư mục 'label' nếu có
for root, dirs, files in os.walk(BAO_DIR):
    for fname in files:
        if fname.endswith('.xlsx') or fname.endswith('.xls') or fname.endswith('.csv'):
            if 'label' in fname.lower() or 'label' in root.lower():
                label_path = os.path.join(root, fname)
                print(f'Tìm thấy label file: {label_path}')
                try:
                    if fname.endswith('.xlsx') or fname.endswith('.xls'):
                        label_df = pd.read_excel(label_path)
                    elif fname.endswith('.csv'):
                        label_df = pd.read_csv(label_path)
                except Exception as e:
                    print(f'Lỗi đọc label: {e}')
                break
    if label_df is not None:
        break""")
            # Fix split lines
            cell['source'] = [line + '\n' for line in source.split('\n')]
            # remove last newline if empty
            if cell['source'][-1] == '\n':
                cell['source'].pop()
            else:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

        # Cell 4: Parse Label File
        elif cell_id == 'cell_04_extract_bao':
            source = "".join(cell['source'])
            source = source.replace("""def parse_label_file(bao_dir):
    \"\"\"
    Đọc file label trong bao_dir.
    Trả về DataFrame với columns: video_name, step, start_frame, end_frame
    (hoặc start_time, end_time tính bằng giây)
    \"\"\"
    label_df = None
    for fname in sorted(os.listdir(bao_dir)):
        if 'label' in fname.lower():
            label_path = os.path.join(bao_dir, fname)
            print(f'Đọc label: {label_path}')
            if fname.endswith('.xlsx') or fname.endswith('.xls'):
                label_df = pd.read_excel(label_path)
            elif fname.endswith('.csv'):
                label_df = pd.read_csv(label_path)
            else:
                with open(label_path, 'r', encoding='utf-8', errors='ignore') as f_:
                    content = f_.read()
                from io import StringIO
                label_df = pd.read_csv(StringIO(content))
            break
    return label_df""", """def parse_label_file(bao_dir):
    label_df = None
    for root, dirs, files in os.walk(bao_dir):
        for fname in sorted(files):
            if fname.endswith('.xlsx') or fname.endswith('.xls') or fname.endswith('.csv'):
                if 'label' in fname.lower() or 'label' in root.lower():
                    label_path = os.path.join(root, fname)
                    print(f'Đọc label: {label_path}')
                    if fname.endswith('.xlsx') or fname.endswith('.xls'):
                        label_df = pd.read_excel(label_path)
                    elif fname.endswith('.csv'):
                        label_df = pd.read_csv(label_path)
                    return label_df
    return label_df""")
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1] == '\n':
                cell['source'].pop()
            else:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')
                
        # Cell 5: Make sure BAO extraction supports nested searching and better column detection
        elif cell_id == 'cell_05_extract_run':
            source = "".join(cell['source'])
            source = source.replace("""    # Lấy danh sách video .mov trong bao_dir
    video_files = {os.path.splitext(f)[0].upper(): os.path.join(bao_dir, f)
                   for f in os.listdir(bao_dir) if f.lower().endswith('.mov')}""", """    # Lấy danh sách video .mov (tìm cả trong thư mục con nếu có)
    video_files = {}
    for root, dirs, files in os.walk(bao_dir):
        for f in files:
            if f.lower().endswith('.mov') or f.lower().endswith('.mp4'):
                video_files[os.path.splitext(f)[0].upper()] = os.path.join(root, f)""")
            cell['source'] = [line + '\n' for line in source.split('\n')]
            if cell['source'][-1] == '\n':
                cell['source'].pop()
            else:
                cell['source'][-1] = cell['source'][-1].rstrip('\n')

with open('Handwash_Train_Colab.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Notebook patched successfully!")

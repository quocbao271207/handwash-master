# handwash-master — thông tin Git

## Repository

- GitHub: https://github.com/quocbao271207/handwash-master
- Nhánh nghiên cứu hiện tại: `main`
- Nhánh lưu trữ toàn bộ dự án cũ: `archive/legacy-research`

## Cấu trúc trên máy

```text
handwash-master/
├── .gitignore                  # Không đưa worktree archive vào main
├── demo.md                     # Nền cho các nghiên cứu tiếp theo
├── GIT_LINK.md                 # Thông tin Git và hướng dẫn khôi phục
└── archive/
    └── legacy-research/        # Git worktree của nhánh cũ
```

## Cập nhật từ GitHub

Tại thư mục `handwash-master`:

```bash
git switch main
git pull --ff-only origin main
git -C archive/legacy-research pull --ff-only origin archive/legacy-research
```

## Lấy lại từ đầu trên máy mới

```bash
git clone https://github.com/quocbao271207/handwash-master.git
cd handwash-master
mkdir -p archive
git worktree add --track -b archive/legacy-research archive/legacy-research origin/archive/legacy-research
```

Nếu local branch `archive/legacy-research` đã tồn tại, dùng:

```bash
git worktree add archive/legacy-research archive/legacy-research
```

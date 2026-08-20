# Downloader Module (`src/downloader/`)

## Responsibility
Manages downloading and temporary local storage of video and image files for posts that pass the interest filter.

## Implementation (`src/downloader/media_downloader.py`)
- Downloads media into `data/raw/` with custom stream chunks.
- Supports both single media items and multi-slide carousel items.
- Provides `cleanup_items()` to delete all media files as soon as the knowledge extraction is complete, ensuring disk space remains near zero.

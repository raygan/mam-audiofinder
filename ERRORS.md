# Error Codes and Debugging Guide

This document provides detailed explanations and solutions for common errors in MAM Audiobook Finder.

## Path Mismatch Errors

### PATH-MISMATCH-001: Source path not found

**Error Message Format:**
```
Failed: HTTP 404 — [PATH-MISMATCH-001] Source path not found
Container path: /media/torrents/Book Title
qBittorrent reports: /downloads/Book Title
```

**What This Means:**
The application cannot find the downloaded files where qBittorrent says they are located. This is almost always caused by incorrect Docker volume mapping between the qBittorrent container and the MAM Audiobook Finder container.

**Common Causes:**

1. **Different volume mounts between containers**
   - qBittorrent saves files to `/downloads` in its container
   - MAM Audiobook Finder looks in `/media/torrents` in its container
   - If these don't point to the same location on your host, files won't be found

2. **MEDIA_ROOT not mounted to both containers**
   - The host directory must be mounted to BOTH containers
   - The mount paths can be different, but must point to the same host location

3. **DL_DIR environment variable doesn't match qBittorrent's save path**
   - Your `DL_DIR` tells the app where to look
   - qBittorrent's save path tells it where to save
   - These must align through proper volume mapping

**How to Debug:**

1. **Check your qBittorrent save path:**
   ```bash
   # In qBittorrent WebUI, check where it saves torrents
   # Look at a completed torrent's "Save path" or "Content path"
   ```

2. **Check your Docker volume mappings:**
   ```yaml
   # docker-compose.yml for qBittorrent
   volumes:
     - /mnt/storage/torrents:/downloads  # Host path : Container path

   # docker-compose.yml for mam-audiofinder
   volumes:
     - /mnt/storage:/media  # Host path : Container path
   ```

3. **Verify the paths align:**
   - qBittorrent saves to `/downloads` → Host: `/mnt/storage/torrents`
   - MAM Audiofinder `DL_DIR=/media/torrents` → Host: `/mnt/storage/torrents`
   - ✅ Both point to same host location!

4. **Check if files actually exist on host:**
   ```bash
   # On your host machine, verify the files exist
   ls -la /mnt/storage/torrents/
   ```

5. **Check if MAM Audiofinder can see the files:**
   ```bash
   docker exec -it mam-audiofinder ls -la /media/torrents/
   ```

**Solutions:**

**Solution 1: Fix your docker-compose.yml volume mappings**

The simplest approach is to mount the same host directory to both containers:

```yaml
# qBittorrent container
volumes:
  - /mnt/storage:/media

# mam-audiofinder container
volumes:
  - /mnt/storage:/media
```

Then set qBittorrent's default save path to `/media/torrents` in its WebUI settings.

**Solution 2: Use QB_INNER_DL_PREFIX to translate paths**

If you can't change your qBittorrent setup, use `QB_INNER_DL_PREFIX` to tell MAM Audiofinder how to translate paths:

```bash
# In your .env file
QB_INNER_DL_PREFIX=/downloads  # What qBittorrent calls it
DL_DIR=/media/torrents          # What MAM Audiofinder calls it
```

The app will translate `/downloads/Book` to `/media/torrents/Book` automatically.

**Solution 3: Use the same paths in both containers**

Mount your host directory to the same container path in both:

```yaml
# Both containers
volumes:
  - /mnt/storage/torrents:/torrents
```

Then:
- Set qBittorrent's save path to `/torrents`
- Set `DL_DIR=/torrents` in MAM Audiofinder

**Still Not Working?**

Check your mappings by running these commands:

```bash
# 1. Get the content_path from qBittorrent's API
docker exec -it qbittorrent cat /path/to/qBittorrent/config/qBittorrent.conf | grep SavePath

# 2. Check what MAM Audiofinder sees
docker exec -it mam-audiofinder env | grep DL_DIR

# 3. List files in both containers
docker exec -it qbittorrent ls -la /downloads/
docker exec -it mam-audiofinder ls -la /media/torrents/
```

If the files show up in qBittorrent but not MAM Audiofinder, your volume mapping is wrong.

---

### PATH-MISMATCH-002: LIB_DIR not accessible

**Error Message Format:**
```
Failed: HTTP 500 — [PATH-MISMATCH-002] Cannot write to library directory
Directory: /media/Books/Audiobooks
```

**What This Means:**
The application cannot write to your library directory. This is usually a permissions issue or the directory doesn't exist.

**Solutions:**

1. **Check if directory exists on host:**
   ```bash
   ls -la /path/to/your/Books/Audiobooks/
   ```

2. **Check permissions:**
   ```bash
   # Directory must be writable by the user running the container
   # Check PUID/PGID in your .env file
   chown -R 1000:1000 /path/to/your/Books/Audiobooks/
   chmod -R 775 /path/to/your/Books/Audiobooks/
   ```

3. **Verify volume mounting:**
   ```yaml
   # docker-compose.yml
   volumes:
     - /path/to/your/Books:/media/Books
   ```

4. **Check from inside container:**
   ```bash
   docker exec -it mam-audiofinder ls -la /media/Books/
   docker exec -it mam-audiofinder touch /media/Books/Audiobooks/test.txt
   ```

---

## Import Errors

### IMPORT-001: No audio files found

**Error Message:**
```
Failed: HTTP 400 — No audio files found to import. Found only .cue files or directory is empty.
```

**What This Means:**
The torrent downloaded successfully, but the app couldn't find any importable audio files.

**Solutions:**

1. **Check what files were downloaded:**
   ```bash
   docker exec -it mam-audiofinder find /media/torrents -name "*.mp3" -o -name "*.m4b" -o -name "*.m4a"
   ```

2. **Verify files aren't exclusively .cue files:**
   - .cue files are metadata files, not audio
   - The app skips these automatically
   - You need actual audio files (.mp3, .m4a, .m4b, .flac, etc.)

---

## qBittorrent Connection Errors

### QB-001: Cannot connect to qBittorrent

**Error Message:**
```
Failed: HTTP 502 — qB connection failed
```

**Solutions:**

1. **Verify QB_URL is correct:**
   ```bash
   # In your .env
   QB_URL=http://qbittorrent:8080
   ```

2. **Check if qBittorrent is running:**
   ```bash
   docker ps | grep qbittorrent
   ```

3. **Test connection from mam-audiofinder container:**
   ```bash
   docker exec -it mam-audiofinder curl http://qbittorrent:8080
   ```

4. **Verify credentials:**
   - Check QB_USER and QB_PASS in .env
   - Try logging into qBittorrent WebUI manually

---

## Permission Errors

### PERM-001: Permission denied during import

**Error Message:**
```
Failed: HTTP 500 — Permission denied when copying files
```

**Solutions:**

1. **Check PUID/PGID settings:**
   ```bash
   # In .env file
   PUID=1000  # Should match your user ID
   PGID=1000  # Should match your group ID

   # Find your user/group ID on host:
   id
   ```

2. **Rebuild container after changing PUID/PGID:**
   ```bash
   docker compose down
   docker compose up -d --build
   ```

3. **Check directory ownership:**
   ```bash
   ls -la /path/to/media/
   # Should show your user:group as owner
   ```

4. **Check UMASK:**
   ```bash
   # In .env
   UMASK=0002  # Allows group write access
   ```

---

## Need More Help?

If you're still stuck after trying these solutions:

1. **Check the logs:**
   ```bash
   docker compose logs -f mam-audiofinder
   ```

2. **Enable debug logging:**
   Add to your .env:
   ```bash
   LOG_LEVEL=DEBUG
   ```

3. **Verify your setup:**
   ```bash
   # Run the built-in health check
   curl http://localhost:8008/health

   # Check configuration
   curl http://localhost:8008/config
   ```

4. **Report the issue:**
   - Go to https://github.com/magrhino/mam-audiofinder/issues
   - Include the full error message
   - Include relevant parts of your docker-compose.yml (remove passwords!)
   - Include the output of `docker compose logs`

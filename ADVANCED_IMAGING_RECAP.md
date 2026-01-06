# Advanced Imaging Recap (Milestone 5B)

## Componenti implementati
- Filter wheel: driver mock/serial + API in server/app.py (init/status/select/filters/wait/statistics/disconnect). Test: test_filter_wheel.py (pass).
- Live stacking: translation alignment + accumulo e salvataggio FITS/PNG (server/live_stacker.py, integrazione in CameraController). API: /api/camera/live-stack/start|stop|status|save. Test: test_live_stacker.py (pass).
- Calibration automation: dark/flat/bias batch con override exposure/gain e metadata FITS (server/calibration.py). API: /api/calibration/start|stop|status. Test: test_calibration.py (pass).
- FITS WCS/output_dir: save_fits accetta output_dir e wcs_info (CRVAL/CRPIX/CDELT/CROTA) per immagini e live stack.

## Endpoint rapidi
- Live stack
  - POST /api/camera/live-stack/start {interval, max_frames, normalize}
  - POST /api/camera/live-stack/stop
  - GET  /api/camera/live-stack/status
  - POST /api/camera/live-stack/save {filename?, fmt=fits|png, target?, ra?, dec?, pixel_scale_arcsec?, rotation_deg?, output_dir?}
- Calibration
  - POST /api/calibration/start {calib_type: dark|flat|bias, count, interval, exposure?, gain?, output_dir?, metadata?}
  - POST /api/calibration/stop
  - GET  /api/calibration/status
- Filter wheel (già in app.py)
  - POST /api/filter-wheel/init {port?, mock?}
  - GET  /api/filter-wheel/status
  - POST /api/filter-wheel/select/{position}
  - GET  /api/filter-wheel/filters
  - GET  /api/filter-wheel/wait/{position}
  - GET  /api/filter-wheel/statistics
  - POST /api/filter-wheel/disconnect

## Test eseguiti (locali)
- /usr/local/bin/python3 test_filter_wheel.py (precedente, green)
- /usr/local/bin/python3 test_live_stacker.py (green)
- /usr/local/bin/python3 test_calibration.py (green)

## Note operative
- Live stack e calibrazione usano camera_controller: con hardware reale serve una camera aperta; i test mockano frame e save_fits.
- WCS: passare ra/dec e pixel_scale_arcsec per valorizzare CRVAL/CRPIX/CDELT/CROTA; rotation_deg opzionale.
- Output dir: tutte le funzioni accettano output_dir per separare stack/calibrazioni da immagini standard.

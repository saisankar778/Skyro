# AreoDrone Backend

## Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set your drone connection string in `main.py` (default: `127.0.0.1:14550` for SITL/simulator).

3. (Optional) Update `HOME_LOCATION` and `BLOCK_COORDINATES` in `main.py` as needed.

4. Run the backend server:
   ```bash
   python main.py
   ```

## API Endpoints

### POST `/api/launch`
Launch a delivery mission to a specified block (A, B, or C).

**Request JSON:**
```json
{
  "block": "A"
}
```

**Response:**
- `{ "status": "Mission completed" }` on success
- `{ "error": "..." }` on error

### GET `/api/status`
Get current drone status (armed, mode, altitude).

**Response:**
```json
{
  "armed": true,
  "mode": "GUIDED",
  "altitude": 10.0
}
```

## Notes
- The backend uses CherryPy and DroneKit to control the drone.
- User notification is a placeholder; integrate with your preferred notification system as needed.
- For real drone use, update the connection string and test safety features.

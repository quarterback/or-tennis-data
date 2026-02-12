# Investigating TennisReporting API for Complete Data

## Current API Endpoint
- `https://api.v2.tennisreporting.com/report/school/{school_id}`
- Parameters: `year`, `genderId`, `isNotVarsity`
- **Problem**: Does NOT return S4/D4 flight data

## How to Find Additional API Endpoints

### 1. Browser DevTools Investigation
1. Go to https://www.tennisreporting.com/
2. Search for Catlin Gabel School
3. Open Chrome DevTools (F12) → Network tab
4. Clear network log and refresh the page
5. Look for XHR/Fetch requests that contain match data
6. Check if there are requests with "match", "flight", "individual" in the URL

### 2. Check for Different Endpoints
Possible alternative endpoints to test:
- `/report/matches` - might have individual match details
- `/report/team` - might have different data structure
- `/matches/school` - different organization
- `/school/{id}/matches` - RESTful pattern

### 3. Check API Response Headers
- Look for pagination headers (X-Total-Count, Link)
- Check if there's a `limit` or `offset` parameter needed
- See if there's a version parameter (v2, v3, etc.)

### 4. Test Different Parameters
Current params: `year`, `genderId`, `isNotVarsity`
Try adding:
- `includeFlight4=true`
- `allFlights=true`
- `detailed=true`
- `full=true`

## Next Steps
1. Upload the PDF to compare expected vs actual data
2. Visit TennisReporting website and inspect network traffic
3. Test alternative API endpoints
4. If API doesn't provide data, consider web scraping

# Action Items API Documentation

## Overview
This API provides endpoints for speech transcription, terminology extraction, meeting minutes generation, and action item management for the construction industry.

## Base URL
```
http://localhost:8000/api/v1
```

## Authentication
Currently, no authentication is required. This should be implemented before production deployment.

## Endpoints

### Terms Management

#### Extract Terms from PDF
```
POST /terms/extract-from-pdf
```
- **Description**: Extract construction industry terms from a PDF file
- **Request**: Multipart form with PDF file
- **Response**: Task creation confirmation

#### Search Terms
```
GET /terms/search
```
- **Parameters**:
  - `query` (string): Search query
  - `limit` (int, optional): Number of results (default: 10)
  - `threshold` (float, optional): Similarity threshold (default: 0.8)
- **Response**: List of matching terms with similarity scores

### Transcription

#### Transcribe Audio
```
POST /transcription/transcribe
```
- **Description**: Transcribe audio file using Whisper
- **Request**: 
  - Multipart form with audio file (mp3, mp4, wav, m4a, flac, ogg)
  - `apply_correction` (boolean): Apply terminology correction
  - `language` (string): Language code (default: "ja")
- **Response**: Task ID and status URL

#### Check Transcription Status
```
GET /transcription/status/{task_id}
```
- **Response**: Current status of transcription task

#### Get Transcription Result
```
GET /transcription/{transcription_id}
```
- **Response**: Complete transcription with segments

### Meeting Minutes

#### Generate Meeting Minutes
```
POST /meetings/generate
```
- **Request Body**:
```json
{
  "transcription_id": 1,
  "meeting_title": "第5回工程会議",
  "meeting_date": "2024-01-15T00:00:00",
  "participants": ["田中", "山田", "佐藤"]
}
```
- **Response**: Meeting minutes ID

#### Get Meeting Minutes
```
GET /meetings/{minutes_id}
```
- **Response**: Complete meeting minutes with action items

#### List Meetings
```
GET /meetings/
```
- **Parameters**:
  - `skip` (int): Offset for pagination
  - `limit` (int): Number of results
- **Response**: List of meetings

### Action Items

#### List Action Items
```
GET /action-items/
```
- **Parameters**:
  - `status` (string, optional): Filter by status
  - `priority` (string, optional): Filter by priority
  - `assignee` (string, optional): Filter by assignee
  - `skip` (int): Offset for pagination
  - `limit` (int): Number of results
- **Response**: List of action items

#### Get Action Item
```
GET /action-items/{item_id}
```
- **Response**: Detailed action item information

#### Update Action Item Status
```
PATCH /action-items/{item_id}/status
```
- **Request Body**:
```json
{
  "status": "completed"
}
```
- **Valid statuses**: pending, in_progress, completed, cancelled

#### Update Action Item
```
PATCH /action-items/{item_id}
```
- **Request Body** (all fields optional):
```json
{
  "title": "Updated title",
  "description": "Updated description",
  "assignee": "新担当者",
  "due_date": "2024-02-01T00:00:00",
  "priority": "high"
}
```

#### Get Related Items
```
GET /action-items/{item_id}/related
```
- **Parameters**:
  - `limit` (int): Number of related items
- **Response**: List of related action items based on tags

#### Search by Tags
```
GET /action-items/by-tags
```
- **Parameters**:
  - `tags` (string): Comma-separated list of tags
- **Response**: Action items matching all specified tags

#### Get Overdue Items
```
GET /action-items/overdue
```
- **Response**: List of overdue action items sorted by days overdue

### Tags

#### List Tags
```
GET /tags/
```
- **Parameters**:
  - `category` (string, optional): Filter by category
- **Response**: List of tags with usage count

#### Get Tag Statistics
```
GET /tags/statistics
```
- **Response**: Tag usage statistics

#### Suggest Tags
```
GET /tags/suggest
```
- **Parameters**:
  - `query` (string): Partial tag name
  - `limit` (int): Number of suggestions
- **Response**: List of tag suggestions

#### Get Items by Tag
```
GET /tags/{tag_name}/items
```
- **Response**: All action items with the specified tag

## Error Responses

All endpoints return appropriate HTTP status codes:
- `200`: Success
- `400`: Bad Request
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

Error response format:
```json
{
  "detail": "Error message"
}
```

## WebSocket Support (Future Enhancement)

For real-time transcription and updates, WebSocket endpoints can be added:
- `/ws/transcription`: Real-time audio transcription
- `/ws/updates`: Real-time action item updates

## Rate Limiting

Currently not implemented. Should be added before production deployment.

## Batch Operations

For efficiency, batch endpoints can be added:
- Batch PDF processing
- Batch action item updates
- Batch tag operations
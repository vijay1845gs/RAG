# PHASE 5 — Document Management QA Testing Guide

## 📋 Pre-Test Setup

1. Ensure backend is running: `python -m uvicorn backend.app.main:app --reload`
2. Ensure frontend dev server is running: `npm run dev`
3. Ensure Supabase is configured (or using local setup)
4. Create a test user account and login

---

## 🧪 QA Test Cases

### Test 1: Upload Document
**Objective:** Verify document upload workflow
**Steps:**
1. Navigate to `/upload`
2. Select or create a collection (e.g., "Test Collection")
3. Drag-and-drop or click to select a PDF file
4. Click "Upload"
5. Verify success state with document metadata displayed
6. Verify document appears in sidebar uploads

**Expected Results:**
- ✅ Upload progress bar displays
- ✅ Success modal shows document ID, filename, page count, chunk count
- ✅ "Ask questions about this document" button navigates to chat
- ✅ Document metadata stored in database

---

### Test 2: View Documents List
**Objective:** Verify Documents page displays uploads correctly
**Steps:**
1. Navigate to `/documents`
2. Wait for page to load
3. Verify all uploaded documents appear in the table

**Expected Results:**
- ✅ Table shows filename, collection, upload date, pages, chunks, status
- ✅ Documents counter matches actual count
- ✅ Status badges show correct color (green for completed, amber for processing)
- ✅ Hover effects and animations work smoothly

---

### Test 3: Search Documents
**Objective:** Verify search functionality works
**Steps:**
1. On Documents page, type in search box (e.g., partial filename)
2. Verify table filters in real-time
3. Clear search box
4. Verify all documents reappear

**Expected Results:**
- ✅ Search filters documents by filename substring
- ✅ Pagination resets to page 1
- ✅ Results update immediately (no lag)
- ✅ "No documents match" message appears if no results

---

### Test 4: Sort Documents
**Objective:** Verify column sorting works
**Steps:**
1. Click on column header (e.g., "Filename")
2. Verify documents sort in ascending order
3. Click same header again
4. Verify documents sort in descending order
5. Test with different columns: Uploaded, Chunks, Status

**Expected Results:**
- ✅ Arrow indicator shows sort direction
- ✅ Documents actually sort in correct order
- ✅ Pagination resets
- ✅ All columns support sorting

---

### Test 5: Filter by Collection
**Objective:** Verify collection filter works
**Steps:**
1. Click collection dropdown (Folder icon)
2. Select a specific collection
3. Verify only documents from that collection appear
4. Select "All collections"
5. Verify all documents reappear

**Expected Results:**
- ✅ Dropdown shows all available collections
- ✅ Collection names display correctly
- ✅ Filtering works immediately
- ✅ Document count matches collection contents

---

### Test 6: Pagination
**Objective:** Verify pagination controls work
**Steps:**
1. Upload 25+ documents to test pagination
2. Set page limit to 10
3. Verify first page shows 10 documents
4. Click "Next" button (>) or page 2
5. Verify page 2 displays next 10 documents
6. Click "Previous" button (<)
7. Verify back on page 1
8. Try changing limit to 20, 50, 100

**Expected Results:**
- ✅ Pagination controls appear when needed
- ✅ Page numbers display correctly
- ✅ Previous/Next buttons enable/disable appropriately
- ✅ Changing limit resets to page 1
- ✅ Page counter shows "Page X of Y (Total)"

---

### Test 7: Open Action Menu
**Objective:** Verify action menu appears
**Steps:**
1. Hover over any document row
2. Click the three-dot menu (⋮) button on the right
3. Verify menu appears with options:
   - Preview
   - Rename
   - Move Collection
   - Delete (in red)

**Expected Results:**
- ✅ Menu appears below or near the button
- ✅ All 4 options visible
- ✅ Menu closes when clicking elsewhere
- ✅ Menu shows on hover of three-dot button

---

### Test 8: Preview Document
**Objective:** Verify preview modal displays document metadata
**Steps:**
1. Click the three-dot menu on a document
2. Select "Preview"
3. Verify modal shows:
   - Filename
   - Document ID (with copy button)
   - Collection name
   - Pages
   - Chunks
   - File size
   - Upload date
   - Status badge

**Expected Results:**
- ✅ Preview modal opens smoothly with animation
- ✅ All metadata displays correctly
- ✅ Copy button copies document ID to clipboard
- ✅ Toast notification shows "Copied to clipboard"
- ✅ Close button or clicking background closes modal

---

### Test 9: Rename Document
**Objective:** Verify document rename functionality
**Steps:**
1. Click the three-dot menu on a document
2. Select "Rename"
3. Verify modal appears with input field
4. Enter new filename (e.g., "My Updated PDF.pdf")
5. Click "Rename" button
6. Verify success toast: "Document renamed successfully"
7. Verify document row updates with new filename immediately
8. Refresh page and verify filename persisted

**Expected Results:**
- ✅ Rename modal appears with input field
- ✅ Input field pre-filled with current filename
- ✅ Rename button disabled if input is empty
- ✅ Success toast appears
- ✅ Table updates immediately
- ✅ Persistence verified after refresh

---

### Test 10: Move Document to Collection
**Objective:** Verify move-to-collection functionality
**Steps:**
1. Upload document to "Collection A"
2. Click three-dot menu
3. Select "Move Collection"
4. Verify modal with dropdown selector
5. Select "Collection B" from dropdown
6. Click "Move" button
7. Verify success toast
8. Verify document row shows new collection badge
9. Filter by "Collection A" and verify document is gone
10. Filter by "Collection B" and verify document is there

**Expected Results:**
- ✅ Move modal appears with collection dropdown
- ✅ Dropdown shows all collections
- ✅ Move button enabled only when collection selected
- ✅ Success toast appears
- ✅ Collection badge updates immediately
- ✅ Filtering confirms document moved
- ✅ Database persisted

---

### Test 11: Delete Document Confirmation
**Objective:** Verify delete confirmation modal
**Steps:**
1. Click three-dot menu on a document
2. Select "Delete"
3. Verify confirmation modal appears showing:
   - Warning message
   - Document filename in bold
   - "Cancel" and "Delete" buttons
   - "Delete" button is red

**Expected Results:**
- ✅ Modal clearly warns about irreversible deletion
- ✅ Shows specific filename being deleted
- ✅ Explains it will remove chunks from vector store
- ✅ Cancel button closes modal without deletion
- ✅ Delete button has red color (danger action)

---

### Test 12: Delete Document Execution
**Objective:** Verify complete document deletion workflow
**Steps:**
1. Note the document ID and filename to delete
2. Open preview to confirm document details
3. Click three-dot menu → Delete
4. Click "Delete" button in confirmation modal
5. Verify success toast: "Document deleted successfully"
6. Verify document disappears from table immediately
7. Verify counter decreases
8. Filter by collection document was in - verify it's gone
9. Check Documents page after refresh - verify deletion persists
10. Check that no orphaned chunks remain (check vector store)

**Expected Results:**
- ✅ Success toast appears immediately
- ✅ Document row disappears from table
- ✅ Total counter decreases
- ✅ Pagination adjusts if needed
- ✅ Search results update
- ✅ Deletion persists after refresh
- ✅ Vector store chunks cleaned up
- ✅ Storage files cleaned up

---

### Test 13: Dashboard Integration
**Objective:** Verify Dashboard reflects document changes
**Steps:**
1. Note current document count on Dashboard
2. Upload a new document
3. Navigate to Dashboard
4. Verify document count increased
5. Verify document appears in "Documents by Collection"
6. Delete a document from Documents page
7. Go back to Dashboard
8. Verify count decreased

**Expected Results:**
- ✅ Dashboard stats update after upload
- ✅ "Documents by Collection" shows updated counts
- ✅ Stats decrease after deletion
- ✅ Latest collection widget shows current collection

---

### Test 14: Responsive Design
**Objective:** Verify responsive layout on mobile
**Steps:**
1. Open DevTools and set to mobile viewport (375px width)
2. Navigate to Documents page
3. Verify:
   - Table stacks responsively
   - All controls visible and usable
   - Modals still display properly
   - Search works on mobile

**Expected Results:**
- ✅ Layout adapts to narrow screens
- ✅ All buttons clickable on touch
- ✅ No horizontal scroll needed
- ✅ Modals centered and properly sized

---

### Test 15: Error Handling
**Objective:** Verify error states and recovery
**Steps:**
1. Simulate network error by opening DevTools Network tab
2. Throttle to offline
3. Try to load documents
4. Verify error message appears
5. Re-enable network
6. Click refresh
7. Verify documents load successfully

**Expected Results:**
- ✅ Error message displays when API fails
- ✅ Error message is informative
- ✅ Refresh button works after recovery
- ✅ No data loss on error

---

### Test 16: Multi-User Isolation
**Objective:** Verify user_id scoping works (if multi-user available)
**Steps:**
1. Login as User A
2. Upload a document
3. Note document ID
4. Logout
5. Login as User B
6. Go to Documents page
7. Verify User A's document does NOT appear

**Expected Results:**
- ✅ User A and User B have separate document lists
- ✅ User B cannot see User A's documents
- ✅ Proper isolation at API level

---

## 📊 Performance Checklist

- [ ] Page loads in < 2 seconds
- [ ] Search provides instant feedback (< 500ms)
- [ ] Pagination feels responsive
- [ ] Modal animations are smooth (60fps)
- [ ] No console errors
- [ ] No memory leaks on repeated actions
- [ ] Database queries are efficient (no N+1)

---

## 🐛 Known Issues / Notes

### Vector Store Cleanup
- ChromaDB deletion uses metadata filter by `document_id`
- Ensure chunks are properly tagged with document metadata during upload
- FAISS deletion support to be added in future phase

### Edge Cases
- Very long filenames may truncate in table
- Special characters in filenames should be handled
- Concurrent deletes of same document should be prevented

---

## ✨ Sign-Off

Once all tests pass, Phase 5 is complete:
- [x] Document lifecycle management (upload, list, filter, preview, rename, delete, move)
- [x] Production-grade UI with search, sort, pagination
- [x] Proper error handling and UX
- [x] Vector store integration for cleanup
- [x] Dashboard integration
- [x] Architecture preservation (auth, chat, collections, history)

---

**Date Tested:** ___________
**Tester:** ___________
**Status:** ___________

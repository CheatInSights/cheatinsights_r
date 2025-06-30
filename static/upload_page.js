document.addEventListener('DOMContentLoaded', function() {
    console.log("Document loaded");
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileList = document.getElementById('fileList');
    const fileItems = document.getElementById('fileItems');
    const uploadButton = document.getElementById('uploadButton');
    const uploadProgress = document.getElementById('uploadProgress');
    const progressBar = document.querySelector('.progress-bar');
    const uploadStatus = document.getElementById('uploadStatus');
    const results = document.getElementById('results');
    const reconstructedDocument = document.getElementById('reconstructedDocument');
    const rsidLegend = document.getElementById('rsidLegend');
    const selectedRSID = document.getElementById('selected_RSID');
    const selectedColour = document.getElementById('rsid_color');
    const documentTabs = document.getElementById('documentTabs');
    const graphContainer = document.getElementById('graphContainer');
    const tableSearch = document.getElementById('tableSearch');


    let selectedFiles = [];
    let documentResults = {};
    let globalResponse = null; // Global variable to store the full response
    let metricsDictionary = {};

    // Initialize search functionality
    if (tableSearch) {
        tableSearch.addEventListener('input', filterTable);
    }

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    // Highlight drop zone when item is dragged over itg
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);

    function filterTable() {
        const searchTerm = tableSearch.value.toLowerCase();
        const tableRows = document.querySelectorAll('#documentTabs tr');
        
        tableRows.forEach(row => {
            const text = row.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                row.classList.remove('hidden');
            } else {
                row.classList.add('hidden');
            }
        });
    }

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    function highlight(e) {
        dropZone.classList.add('dragover');
    }

    function unhighlight(e) {
        dropZone.classList.remove('dragover');
    }

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    function handleFiles(files) {
        const docxFiles = Array.from(files).filter(file => file.name.endsWith('.docx'));
        if (docxFiles.length > 0) {
            addFiles(docxFiles);
        } else {
            alert('Please upload .docx files');
        }
    }

    function addFiles(files) {
        files.forEach(file => {
            if (!selectedFiles.find(f => f.name === file.name)) {
                selectedFiles.push(file);
            }
        });
        updateFileList();
        updateFileInfo();
    }

    function removeFile(fileName) {
        selectedFiles = selectedFiles.filter(file => file.name !== fileName);
        updateFileList();
        updateFileInfo();
    }

    // Make removeFile globally accessible
    window.removeFile = removeFile;

    function updateFileList() {
        if (selectedFiles.length === 0) {
            fileList.style.display = 'none';
            return;
        }

        fileList.style.display = 'block';
        fileItems.innerHTML = '';

        selectedFiles.forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                    <span class="file-name">${file.name}</span>
                    <span class="file-size">${formatFileSize(file.size)}</span>
                    <button type="button" class="remove-file" onclick="removeFile('${file.name}')">Remove</button>
                `;
            fileItems.appendChild(fileItem);
        });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function updateFileInfo() {
        if (selectedFiles.length === 0) {
            fileInfo.textContent = 'No files chosen';
            uploadButton.disabled = true;
        } else if (selectedFiles.length === 1) {
            fileInfo.textContent = `Selected file: ${selectedFiles[0].name}`;
            uploadButton.disabled = false;
        } else {
            fileInfo.textContent = `Selected ${selectedFiles.length} files`;
            uploadButton.disabled = false;
        }
    }

    function createLegend(rsidColors) {
        rsidLegend.innerHTML = '';
        Object.entries(rsidColors).forEach(([rsid, color]) => {
            const legendItem = document.createElement('div');
            legendItem.className = 'legend-item';
            legendItem.innerHTML = `
                    <div class="legend-color" style="background-color: ${color}"></div>
                    <span>RSID: ${rsid}</span>
                `;
            rsidLegend.appendChild(legendItem);
        });
    }

    function createDocumentTabs() {
        documentTabs.innerHTML = '';
        Object.keys(documentResults).forEach((fileName, index) => {
            const result = documentResults[fileName];
            const metadata = result.metadata || {};
            const metrics = result.metrics || {};
            
            // Extract metadata information
            const coreProps = metadata.core_properties || {};
            const docxCoreProps = metadata.docx_core_properties || {};
            
            // Get creator information
            const creator = coreProps.creator || docxCoreProps.author || 'Unknown';
            
            // Get last modified by
            const lastModifiedBy = coreProps.last_modified_by || docxCoreProps.last_modified_by || 'Unknown';
            
            // Get dates
            const createdOn = coreProps.created || docxCoreProps.created || 'Unknown';
            const lastModified = coreProps.modified || docxCoreProps.modified || 'Unknown';
            
            // Format dates
            const formatDate = (dateString) => {
                if (dateString === 'Unknown') return 'Unknown';
                try {
                    const date = new Date(dateString);
                    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                } catch (e) {
                    return dateString;
                }
            };
            
            // Get suspicion score
            const suspicionScore = metrics.score || 0;
            const scoreClass = suspicionScore > 70 ? 'high' : suspicionScore > 40 ? 'medium' : 'low';
            
            // Create table row
            const row = document.createElement('tr');
            row.className = index === 0 ? 'active' : '';
            row.onclick = () => window.selectDocument(fileName);
            
            row.innerHTML = `
                <td class="file-filename">${fileName}</td>
                <td class="file-creator">${creator}</td>
                <td class="file-modified-by">${lastModifiedBy}</td>
                <td class="file-date">${formatDate(createdOn)}</td>
                <td class="file-date">${formatDate(lastModified)}</td>
                <td class="file-suspicion-score ${scoreClass}">${suspicionScore}%</td>
                <td class="file-actions">
                    <button class="btn btn-sm btn-outline-primary" onclick="event.stopPropagation(); window.switchDocument('${fileName}')">
                        View
                    </button>
                </td>
            `;
            
            documentTabs.appendChild(row);
        });
    }

    window.selectDocument = function(fileName) {
        // console.log('1. selectDocument called with:', fileName);
        // Update active row
        document.querySelectorAll('#documentTabs tr').forEach(row => {
            row.classList.remove('active');
        });
        
        // Find and activate the clicked row
        const rows = document.querySelectorAll('#documentTabs tr');
        for (let row of rows) {
            const filenameCell = row.querySelector('.file-filename');
            if (filenameCell && filenameCell.textContent === fileName) {
                row.classList.add('active');
                break;
            }
        }

        // Display selected document
        displayDocument(fileName);
        
    };

    window.switchDocument = function(fileName) {
        // Update active row
        document.querySelectorAll('#documentTabs tr').forEach(row => {
            row.classList.remove('active');
        });
        
        // Find and activate the clicked row
        const rows = document.querySelectorAll('#documentTabs tr');
        for (let row of rows) {
            const filenameCell = row.querySelector('.file-filename');
            if (filenameCell && filenameCell.textContent === fileName) {
                row.classList.add('active');
                break;
            }
        }

        // Display selected document
        displayDocument(fileName);
        
        // // Simulate clicking the Focus button to switch to singleview page
        const focusButton = document.getElementById('singleview_button');
        if (focusButton) {
            focusButton.click();
        }
    };

    function displayDocument(fileName) {
        // console.log('2. displayDocument called with:', fileName);
        const result = documentResults[fileName];
        if (result && result.html) {
            // Extract the style section from the HTML
            const styleMatch = result.html.match(/<style>([\s\S]*?)<\/style>/);
            if (styleMatch) {
                // Remove existing styles for this document
                const existingStyle = document.querySelector(`style[data-document="${fileName}"]`);
                if (existingStyle) {
                    existingStyle.remove();
                }

                // Add the styles to the document
                const styleSheet = document.createElement('style');
                styleSheet.setAttribute('data-document', fileName);
                styleSheet.textContent = styleMatch[1];
                document.head.appendChild(styleSheet);
            }

            // Extract the body content
            const bodyMatch = result.html.match(/<body>([\s\S]*?)<\/body>/);
            if (bodyMatch) {
                reconstructedDocument.innerHTML = bodyMatch[1];
                attachRunListeners();
            }

            // Create legend from the data
            const rsidColors = {};
            result.data.forEach(para => {
                para.runs.forEach(run => {
                    if (run.rsid) {
                        const runElement = reconstructedDocument.querySelector(`[data-rsid="${run.rsid}"]`);
                        if (runElement) {
                            const color = window.getComputedStyle(runElement).backgroundColor;
                            rsidColors[run.rsid] = color;
                        }
                    }
                });
            });
            createLegend(rsidColors);

            // Display RSID information from settings.xml
            if (result.settings_rsids) {
                displayRsidList(result.settings_rsids);
            }

            // Display metadata
            if (result.metadata) {
                displayMetadata(result.metadata);
            }

            // Display suspicion score
            if (result.metrics) {
                // console.log('3. Metrics for this document:', JSON.stringify(result.metrics, null, 2));
                displaySuspicionScore(result.metrics);
            }
        }
    }

    function displayMetadata(metadata) {
        const metadataList = document.getElementById('metadataList');
        metadataList.innerHTML = '';

        // Helper to create a section
        function createSection(title, dataObj) {
            if (!dataObj || Object.keys(dataObj).length === 0) return null;
            const section = document.createElement('div');
            section.className = 'metadata-section';

            // Collapsible header
            const header = document.createElement('div');
            header.className = 'metadata-section-header';
            header.textContent = title;
            header.onclick = function () {
                content.style.display = content.style.display === 'none' ? '' : 'none';
            };
            section.appendChild(header);

            // Content
            const content = document.createElement('div');
            content.className = 'metadata-section-content';
            content.style.display = '';
            for (const [key, value] of Object.entries(dataObj)) {
                const item = document.createElement('div');
                item.className = 'metadata-item';
                const keySpan = document.createElement('span');
                keySpan.className = 'metadata-key';
                keySpan.textContent = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
                const valueSpan = document.createElement('span');
                valueSpan.className = 'metadata-value';
                valueSpan.textContent = value === null ? '' : value;
                item.appendChild(keySpan);
                item.appendChild(valueSpan);
                content.appendChild(item);
            }
            section.appendChild(content);
            return section;
        }

        // Render each section
        const sections = [
            ['Core Properties', metadata.core_properties],
            ['App Properties', metadata.app_properties],
            ['Custom Properties', metadata.custom_properties],
            ['python-docx Core Properties', metadata.docx_core_properties],
            ['python-docx Custom Properties', metadata.docx_custom_properties],
        ];
        let anySection = false;
        for (const [title, data] of sections) {
            const section = createSection(title, data);
            if (section) {
                metadataList.appendChild(section);
                anySection = true;
            }
        }
        if (!anySection) {
            metadataList.textContent = 'No metadata found.';
        }
    }

    // Add minimal CSS for collapsible sections
    const style = document.createElement('style');
    style.textContent = `
        .metadata-section {
        margin-bottom: 10px;
        border: 1px solid #eee;
        border-radius: 4px;
        background: #fafbfc;
        }
        .metadata-section-header {
        font-weight: bold;
        background: #f1f3f4;
        padding: 6px 10px;
        cursor: pointer;
        border-bottom: 1px solid #eee;
        user-select: none;
        }
        .metadata-section-content {
        padding: 6px 10px;
        }
        
        /* Suspicion Score Styles */
        .suspicion-score-container {
        background: #f8f9fa;
        margin-top: 15px;
        }
        
        .score-display {
        text-align: center;
        margin-bottom: 20px;
        padding: 15px;
        background: white;
        border-radius: 6px;
        border: 2px solid #e9ecef;
        }
        
        .main-score {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 5px;
        }
        
        .score-value {
        color: #dc3545;
        font-size: 28px;
        }
        
        .total-score {
        font-size: 14px;
        color: #6c757d;
        }
        
        .factors-section {
        margin-bottom: 20px;
        }
        
        .factors-section h4 {
        color: #495057;
        margin-bottom: 10px;
        font-size: 16px;
        }
        
        .factors-list {
        list-style: none;
        padding: 0;
        margin: 0;
        }
        
        .factors-list li {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 4px;
        padding: 8px 12px;
        margin-bottom: 8px;
        color: #856404;
        font-size: 14px;
        }
        
        .statistics-section h4 {
        color: #495057;
        margin-bottom: 15px;
        font-size: 16px;
        }
        
        .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 12px;
        }
        
        .stat-item {
        background: white;
        border: 1px solid #dee2e6;
        border-radius: 4px;
        padding: 10px 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        }
        
        .stat-label {
        font-weight: 500;
        color: #495057;
        font-size: 14px;
        }
        
        .stat-value {
        font-weight: bold;
        color: #007bff;
        font-size: 14px;
        }
        `;
    document.head.appendChild(style);

    function displayRsidList(rsidData) {
        const rsidStats = document.getElementById('rsidStats');
        const rsidTableBody = document.getElementById('rsidTableBody');

        // Update stats
        rsidStats.textContent = `Total unique RSIDs: ${rsidData.total_count}`;

        // Clear existing table content
        rsidTableBody.innerHTML = '';

        // Add each RSID to the table
        rsidData.rsids.forEach(rsid => {
            const row = document.createElement('tr');
            row.innerHTML = `
                    <td>${rsid.value}</td>
                    <td>${rsid.sources.join(', ')}</td>
                    <td class="text-nowrap">
                        <button class="btn btn-sm btn-outline-primary rsid-action-btn" 
                                onclick="highlightRsid('${rsid.value}')" title="Highlight RSID">
                            H
                        </button>
                        <button class="btn btn-sm btn-outline-secondary rsid-action-btn" 
                                onclick="hideRsid('${rsid.value}')" title="Hide RSID">
                            X
                        </button>
                    </td>
                `;
            rsidTableBody.appendChild(row);
        });
    }

    // Global functions that need to be accessible from onclick attributes
    window.highlightRsid = function(rsidValue) {
        console.log('highlightRsid called with:', rsidValue);
        
        // Remove previous highlights
        document.querySelectorAll('.rsid-highlight').forEach(el => {
            el.classList.remove('rsid-highlight');
        });

        // Highlight all elements with this RSID
        const elements = document.querySelectorAll(`[data-rsid="${rsidValue}"]`);
        console.log('Found elements to highlight:', elements.length);
        elements.forEach(el => {
            el.classList.add('rsid-highlight');
        });

        // Update selected RSID display
        const selectedRSID = document.getElementById('selected_RSID');
        if (selectedRSID) {
            selectedRSID.innerHTML = rsidValue;
            window.flashGreenDiv(selectedRSID);
        } else {
            console.log('selected_RSID element not found');
        }
    };

    window.hideRsid = function(rsidValue) {
        console.log('hideRsid called with:', rsidValue);
        
        const elements = document.querySelectorAll(`[data-rsid="${rsidValue}"]`);
        console.log('Found elements to hide:', elements.length);
        elements.forEach(el => {
            el.style.backgroundColor = 'rgba(255, 255, 255, 0)';
        });
    };

    window.flashGreenDiv = function(element) {
        // Store original background
        let originalBg = element.style.backgroundColor || 'var(--bs-bg-secondary)';

        // Flash green
        element.style.backgroundColor = 'rgb(27, 254, 84)';

        // Return to original after 0.7 seconds
        setTimeout(() => {
            element.style.backgroundColor = originalBg;
        }, 700);
    };

    window.getSelectedColour = function() {
        const selectedColour = document.getElementById('rsid_color');
        if (selectedColour) {
            console.log("colour \n")
            console.log(selectedColour.value)
            return selectedColour.value;
        }
        return '#ff0000'; // default color
    };

    window.getAllWithRSID = function(rsid) {
        const reconstructedDocument = document.getElementById('reconstructedDocument');
        if (reconstructedDocument) {
            return reconstructedDocument.querySelectorAll(`.run[data-rsid="${rsid}"]`);
        }
        return [];
    };

    window.changeColourRsid = function() {
        const selectedRSID = document.getElementById('selected_RSID');
        if (!selectedRSID) return;
        
        let rsid = selectedRSID.innerHTML;
        console.log(rsid);
        let selectedColor = window.getSelectedColour();

        let runs = window.getAllWithRSID(rsid);
        console.log(runs);
        runs.forEach(run => {
            run.style.backgroundColor = selectedColor;
        });
    };

    window.selected_rsid_toggle_hidden = function() {
        const selectedRSID = document.getElementById('selected_RSID');
        if (!selectedRSID) return;
        
        let rsid = selectedRSID.innerHTML;
        let runs = window.getAllWithRSID(rsid);
        
        if (runs.length === 0) return;
        
        // Check if the first run is currently hidden (transparent background)
        const firstRun = runs[0];
        const currentBg = firstRun.style.backgroundColor;
        const isHidden = currentBg === 'rgba(255, 255, 255, 0)' || currentBg === 'transparent';
        
        if (isHidden) {
            // Unhide: remove the background color to restore original styling
            runs.forEach(run => {
                run.style.backgroundColor = '';
            });
        } else {
            // Hide: set transparent background
            runs.forEach(run => {
                run.style.backgroundColor = 'rgba(255, 255, 255, 0)';
            });
        }
    };

    window.hideAllRuns = function() {
        const reconstructedDocument = document.getElementById('reconstructedDocument');
        if (!reconstructedDocument) return;
        
        // Get all .run elements in the reconstructed document
        let runs = reconstructedDocument.querySelectorAll('.run');
        runs.forEach(run => {
            run.style.backgroundColor = 'rgba(255, 255, 255, 0)';
        });
    };

    window.unhideAllRuns = function() {
        const reconstructedDocument = document.getElementById('reconstructedDocument');
        if (!reconstructedDocument) return;
        
        // Get all .run elements in the reconstructed document
        let runs = reconstructedDocument.querySelectorAll('.run');
        runs.forEach(run => {
            // Remove the inline backgroundColor style to let the CSS from header take over
            run.style.backgroundColor = '';
        });
    };

    function displaySharedRsids(sharedRsids) {
        const section = document.getElementById('sharedRsidsSection');
        const content = document.getElementById('sharedRsidsContent');
        content.innerHTML = '';

        if (!sharedRsids || Object.keys(sharedRsids).length === 0) {
            section.style.display = 'block';
            content.innerHTML = '<em>No shared RSIDs found between the uploaded documents.</em>';
            return;
        }

        let html = '<table class="shared-rsids-table"><thead><tr><th>RSID</th><th>Documents</th></tr></thead><tbody>';
        for (const [rsid, docs] of Object.entries(sharedRsids)) {
            html += `<tr><td>${rsid}</td><td>${docs.join('<br>')}</td></tr>`;
        }
        html += '</tbody></table>';
        section.style.display = 'block';
        content.innerHTML = html;
    }

    function displaySuspicionScore(suspicionScoreData) {
        const section = document.getElementById('suspicionScoreSection');
        const content = document.getElementById('suspicionScoreContent');
        content.innerHTML = '';

        if (!suspicionScoreData) {
            section.style.display = 'none';
            return;
        }

        let html = '<div class="suspicion-score-container">';
        
        let colour = 'green';
        if (suspicionScoreData.total_score >80 ) {
            colour = 'red';
        }else if (suspicionScoreData.total_score >60){
            colour = 'orange';
        }else if (suspicionScoreData.total_score >40){
            colour = 'yellow';
        };
        // Main score display
        html += '<div class="score-display">';
        html += `<div class="main-score">Suspicion Score: <span class="score-value">${suspicionScoreData.score}%</span></div>`;
        html += `<div class="total-score" style='color: ${colour};'>Raw Score: ${suspicionScoreData.total_score}</div>`;
        html += '</div>';

        // Factors that contributed to the score
        if (suspicionScoreData.factors && suspicionScoreData.factors.length > 0) {
            html += '<div class="factors-section">';
            html += '<h4>Suspicious Factors:</h4>';
            html += '<ul class="factors-list">';
            suspicionScoreData.factors.forEach(factor => {
                html += `<li>${factor}</li>`;
            });
            html += '</ul>';
            html += '</div>';
        }

        // Statistics
        if (suspicionScoreData.statistics) {
            html += '<div class="statistics-section">';
            html += '<h4>Document Statistics:</h4>';
            html += '<div class="stats-grid">';
            html += `<div class="stat-item"><span class="stat-label">Average Chars per RSID:</span> <span class="stat-value">${suspicionScoreData.statistics.average_chars_per_rsid}</span></div>`;
            html += `<div class="stat-item"><span class="stat-value">Average Chars per Run:</span> <span class="stat-value">${suspicionScoreData.statistics.average_chars_per_run}</span></div>`;
            html += `<div class="stat-item"><span class="stat-label">Word Count:</span> <span class="stat-value">${suspicionScoreData.statistics.word_count}</span></div>`;
            html += `<div class="stat-item"><span class="stat-label">Short Paragraphs:</span> <span class="stat-value">${suspicionScoreData.statistics.short_paragraph_count}</span></div>`;
            html += `<div class="stat-item"><span class="stat-label">Unique RSIDs:</span> <span class="stat-value">${suspicionScoreData.statistics.unique_rsid_count}</span></div>`;
            html += `<div class="stat-item"><span class="stat-label">Total Runs:</span> <span class="stat-value">${suspicionScoreData.statistics.total_runs}</span></div>`;
            html += '</div>';
            html += '</div>';
        }

        html += '</div>';

        section.style.display = 'block';
        content.innerHTML = html;
    }

    function displayResults(response) {
        // Store the response globally so other functions can access it
        globalResponse = response;

        if (response.results) {
            documentResults = response.results;
            // console.log(documentResults);
            createDocumentTabs();

            // Display the first document by default
            const firstFileName = Object.keys(documentResults)[0];
            if (firstFileName) {
                displayDocument(firstFileName);
            }
        } else if (response.metrics) {
            // Single file upload - set up documentResults for consistency
            const fileName = selectedFiles[0].name;
            documentResults = {
                [fileName]: {
                    metrics: response.metrics,
                    html: response.html,
                    data: response.data,
                    settings_rsids: response.settings_rsids,
                    metadata: response.metadata
                }
            };
            
            // Create document tabs for single file
            createDocumentTabs();
            
            // Display the single document
            displayDocument(fileName);
        }

        // Display shared RSIDs if present
        if (response.shared_rsids !== undefined) {
            displaySharedRsids(response.shared_rsids);
        }
    }

    fileInput.addEventListener('change', function () {
        if (this.files.length > 0) {
            addFiles(Array.from(this.files));
        }
    });

    // Handle form submission
    document.getElementById('uploadForm').addEventListener('submit', function (e) {
        console.log("Submit Pressed");
        e.preventDefault();

        // Hide shared RSIDs section on new upload
        document.getElementById('sharedRsidsSection').style.display = 'none';

        const formData = new FormData();

        // Add CSRF token
        formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

        // Add all selected files
        selectedFiles.forEach(file => {
            formData.append('documents', file);
        });

        const xhr = new XMLHttpRequest();

        uploadProgress.style.display = 'block';
        uploadButton.disabled = true;
        console.log("reached here");

        xhr.upload.addEventListener('progress', function (e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progressBar.style.width = percentComplete + '%';
            }
        });
        console.log("reached here2");

        xhr.addEventListener('load', function () {
            if (xhr.status === 200) {
                console.log("processing complete");
                uploadStatus.textContent = 'Processing Complete!';
                
                // Remove all children from fileList and hide it
                // const fileList = document.getElementById('fileList');
                
                // if (fileList) {
                //     fileList.innerHTML = '';
                //     fileList.style.display = 'none';
                // }
                
                const response = JSON.parse(xhr.responseText);
                displayResults(response);
                
                // Generate metrics dictionary for both single and multiple file uploads
                generateMetricsDictionary();
            } else {
                const response = JSON.parse(xhr.responseText);
                uploadStatus.textContent = response.error || 'Upload failed. Please try again.';
                uploadButton.disabled = false;
            }
        });

        xhr.addEventListener('error', function () {
            uploadStatus.textContent = 'Upload failed. Please try again.';
            uploadButton.disabled = false;
        });

        xhr.open('POST', '/upload/files/', true);
        xhr.send(formData);
    });

    let selectedRun = null;

    function handleRunClick(event) {
        selectedRun = event.target;
        selectedRSID.innerHTML = selectedRun.getAttribute('data-rsid');
        // console.log(selectedRSID);

        flashGreenDiv(selectedRSID);
    }

    function getRSID(event) {
        value = event.target.getAttribute('data-rsid');
        return value
    }

    function attachRunListeners() {
        reconstructedDocument.querySelectorAll('.run').forEach(run => {
            run.addEventListener('mouseover', function (e) {
                let rsid = getRSID(e);
                // console.log("RSID HOVER\n", rsid)
                let query = getAllWithRSID(rsid);
                query.forEach(run => {
                    run.style.border = '1px solid red';
                });
            });
            run.addEventListener('mouseout', function (e) {
                let rsid = getRSID(e);
                let query = getAllWithRSID(rsid);
                query.forEach(run => {
                    run.style.border = '';
                });
            });
            run.addEventListener('click', handleRunClick);
        });
    }

    // Helper: Extract metric data from document results
    function extractMetricData(filename, metric) {
        if (documentResults.hasOwnProperty(filename)) {
            return { [filename]: documentResults[filename].metrics[metric] };
        }
        return {};
    }

    // Helper: Extract two specific statistics values from all documents
    function getStatisticsXY(statKey1, statKey2) {
        const result = {};

        // Find the statistics array in metricsDictionary
        const statisticsArray = metricsDictionary.statistics;
        if (!statisticsArray) {
            console.log("No statistics found in metricsDictionary");
            return result;
        }

        // Iterate through each statistics object
        statisticsArray.forEach(statObj => {
            const filename = Object.keys(statObj)[0];
            const stats = statObj[filename];

            if (stats && stats[statKey1] !== undefined && stats[statKey2] !== undefined) {
                result[filename] = [stats[statKey1], stats[statKey2]];
            }
        });

        console.log("getStatisticsXY result:", result);
        return result;
    }

    // Helper: Extract a single statistics value from all documents (for count-based plotting)
    function getStatisticsX(statKey) {
        const result = [];

        // Find the statistics array in metricsDictionary
        const statisticsArray = metricsDictionary.statistics;
        if (!statisticsArray) {
            console.log("No statistics found in metricsDictionary");
            return result;
        }

        // Iterate through each statistics object
        statisticsArray.forEach(statObj => {
            const filename = Object.keys(statObj)[0];
            const stats = statObj[filename];

            if (stats && stats[statKey] !== undefined) {
                result.push({ [filename]: stats[statKey] });
            }
        });

        console.log("getStatisticsX result:", result);
        return result;
    }

    // Helper: Calculate mean and standard deviation
    function calculateStats(values) {
        if (values.length === 0) {
            return { mean: 0, stdDev: 0 };
        }
        if (values.length === 1) {
            return { mean: values[0], stdDev: 0 };
        }
        
        const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
        const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
        const stdDev = Math.sqrt(variance);
        return { mean, stdDev };
    }

    // Process raw metric data with optional normalization and ID tagging
    function processMetricData(metricData, normalised = false, count = false) {
        let roundedData = metricData.map(item => {
            const key = Object.keys(item)[0];
            const value = item[key];
            return { [key]: Math.round(value) };
        });

        if (normalised) {
            const values = roundedData.map(item => Object.values(item)[0]);
            const { mean, stdDev } = calculateStats(values);
            
            // Skip normalization if standard deviation is 0 (single data point)
            if (stdDev === 0) {
                console.log('Skipping normalization for single data point');
            } else {
                roundedData = roundedData.map(item => {
                    const key = Object.keys(item)[0];
                    const z = (item[key] - mean) / stdDev;
                    return { [key]: Math.round(z * 100) / 100 };
                });
            }
        }

        if (count) {
            const valueCount = {};
            const idTracker = {};
            roundedData.forEach(item => {
                const key = Object.keys(item)[0];
                const val = item[key];
                valueCount[val] = (valueCount[val] || 0) + 1;
            });

            roundedData = roundedData.map(item => {
                const key = Object.keys(item)[0];
                const val = item[key];
                idTracker[val] = (idTracker[val] || 1);
                const newItem = { [key]: [idTracker[val], val] };
                idTracker[val]++;
                return newItem;
            });
        }

        return roundedData;
    }

    // Draw a scatter plot (optionally with a normal curve)
    function createScatterPlot(dataPoints, isNormalised = false, metricLabel = '', xAxisLabel = 'Value', yAxisLabel = 'ID Count') {
        const chartWrapper = document.createElement('div');
        chartWrapper.className = 'chart-wrapper';

        const canvas = document.createElement('canvas');
        canvas.className = 'chart-canvas';
        chartWrapper.appendChild(canvas);
        graphContainer.appendChild(chartWrapper);

        const chartData = dataPoints.map(item => {
            const key = Object.keys(item)[0];
            const [id, value] = item[key];
            return { x: value, y: id };
        });

        const maxY = Math.max(...chartData.map(p => p.y));
        const yAxisMax = maxY * 2;

        const datasets = [{
            label: 'Data Points',
            data: chartData,
            backgroundColor: 'rgba(255, 0, 0, 1)',
            borderColor: 'rgba(0, 0, 0, 1)',
            pointStyle: 'circle',
            pointRadius: 5,
            pointHoverRadius: 7,
            order: 1  // Higher order = appears on top
        }];

        if (isNormalised) {
            const xVals = chartData.map(p => p.x);
            const { mean, stdDev } = calculateStats(xVals);
            
            // Skip normal distribution for single data point (stdDev = 0)
            if (stdDev === 0) {
                console.log('Skipping normal distribution for single data point');
            } else {
                const minX = Math.min(...xVals);
                const maxX = Math.max(...xVals);
                const peakY = 1 / (stdDev * Math.sqrt(2 * Math.PI));
                const scaleFactor = maxY / peakY;

                // Create multiple datasets for different standard deviation ranges
                const stdDevRanges = [
                    { range: 3, color: 'rgba(255, 100, 0, 0.2)', label: '±3σ' },
                    { range: 2, color: 'rgba(255, 180, 0, 0.4)', label: '±2σ' },
                    { range: 1, color: 'rgba(255, 255, 0, 0.5)', label: '±1σ' }
                ];

                // Add filled areas for each standard deviation range (layered effect)
                stdDevRanges.forEach(({ range, color, label }) => {
                    const fillCurve = [];
                    const startX = mean - (range * stdDev);
                    const endX = mean + (range * stdDev);

                    // Generate curve points for this range
                    for (let x = startX; x <= endX; x += (endX - startX) / 50) {
                        const y = (1 / (stdDev * Math.sqrt(2 * Math.PI))) *
                            Math.exp(-0.5 * Math.pow((x - mean) / stdDev, 2)) * scaleFactor;
                        fillCurve.push({ x, y });
                    }

                    datasets.unshift({
                        label: label,
                        data: fillCurve,
                        type: 'line',
                        borderColor: color.replace(/[\d.]+\)$/, '0.8)'),
                        backgroundColor: color,
                        borderWidth: 1,
                        fill: true,
                        pointRadius: 0,
                        tension: 0.4,
                        order: 3  // Lower order = appears behind
                    });
                });

                // Add the main normal distribution curve on top of fills but behind points
                const curve = [];
                for (let x = minX; x <= maxX; x += (maxX - minX) / 50) {
                    const y = (1 / (stdDev * Math.sqrt(2 * Math.PI))) *
                        Math.exp(-0.5 * Math.pow((x - mean) / stdDev, 2)) * scaleFactor;
                    curve.push({ x, y });
                }

                datasets.unshift({
                    label: 'Normal Distribution',
                    data: curve,
                    type: 'line',
                    borderColor: 'rgba(0, 0, 255, 0.8)',
                    borderWidth: 2,
                    fill: false,
                    pointRadius: 0,
                    tension: 0.4,
                    order: 2  // Between fills and points
                });
            }
        }

        new Chart(canvas, {
            type: 'scatter',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                aspectRatio: 2,
                plugins: {
                    title: {
                        display: true,
                        text: isNormalised ? `Normalised ${metricLabel}` : metricLabel,
                        font: { size: 16, weight: 'bold' },
                        padding: { top: 10, bottom: 20 }
                    },
                    legend: { display: true },
                    tooltip: {
                        callbacks: {
                            title: (ctx) => {
                                const p = ctx[0].parsed;
                                return ctx[0].dataset.label === 'Normal Distribution'
                                    ? `Expected at x = ${p.x.toFixed(2)}`
                                    : `Data Point: x = ${p.x}, y = ${p.y}`;
                            },
                            label: (ctx) => {
                                if (ctx.dataset.label === 'Normal Distribution') {
                                    return `Expected Distribution`;
                                }
                                // For statistics charts, show filename
                                const dataPoint = ctx.parsed;
                                const dataIndex = ctx.dataIndex;
                                const originalData = dataPoints[dataIndex];
                                if (originalData) {
                                    const filename = Object.keys(originalData)[0];
                                    return `File: ${filename}`;
                                }
                                return `Data Point`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        title: { display: true, text: xAxisLabel }
                    },
                    y: {
                        beginAtZero: true,
                        max: yAxisMax,
                        title: { display: true, text: yAxisLabel },
                        ticks: {
                            precision: 0,
                            // Remove stepSize to let Chart.js auto-generate appropriate ticks
                            callback: function (value, index, values) {
                                // Only show every nth tick to avoid overcrowding
                                return index % Math.max(1, Math.floor(values.length / 10)) === 0 ? value : '';
                            }
                        }
                    }
                }
            }
        });
    }

    // Create all charts based on the metricsDictionary
    function createGraphs() {
        const individual = [
            'total_characters_count',
            'total_word_count',
            'total_paragraph_count',
            'total_runs_count',
            'unique_rsid_count'
        ]
        const pair = [
            ['total_characters_count', 'total_runs_count'],
            ['total_characters_count', 'unique_rsid_count'],
            ['total_word_count', 'total_runs_count'],
            ['total_word_count', 'unique_rsid_count'],
            ['total_paragraph_count', 'total_runs_count'],
            ['total_paragraph_count', 'unique_rsid_count'],
            ['unique_rsid_count', 'total_runs_count']
        ]

        Object.entries(metricsDictionary).forEach(([metricKey, data]) => {
            if (metricKey === 'score') {
                const raw = processMetricData(data, false, true);
                // const norm = processMetricData(data, true, true);
                createScatterPlot(raw, true, metricKey);
                // createScatterPlot(norm, true, metricKey);
            }
            if (metricKey === 'total_score') {
                const raw = processMetricData(data, false, true);
                // const norm = processMetricData(data, true, true);
                createScatterPlot(raw, true, metricKey);
                // createScatterPlot(norm, true, metricKey);
            }
            if (metricKey === 'statistics') {

                // Create individual statistics charts (X vs Count)
                individual.forEach(statKey => {
                    const statData = getStatisticsX(statKey);
                    if (statData.length > 0) {
                        const processedData = processMetricData(statData, false, true);
                        const processedDataNormalised = processMetricData(statData, true, true);
                        const chartTitle = `${statKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} Distribution`;
                        const xAxisLabel = statKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        createScatterPlot(processedData, true, chartTitle, xAxisLabel, 'Count');
                        createScatterPlot(processedDataNormalised, true, chartTitle, xAxisLabel, 'Count');
                    }
                });

                // Create XY pair charts
                pair.forEach(([statKey1, statKey2]) => {
                    const pairData = getStatisticsXY(statKey1, statKey2);
                    if (Object.keys(pairData).length > 0) {
                        const data = Object.entries(pairData).map(([filename, [val1, val2]]) => {
                            return { [filename]: [val1, val2] };
                        });
                        const chartTitle = `${statKey1.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} vs ${statKey2.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`;
                        const xAxisLabel = statKey1.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        const yAxisLabel = statKey2.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        // createScatterPlot(data, false, chartTitle, xAxisLabel, yAxisLabel);
                        createScatterPlot(data, true, chartTitle, xAxisLabel, yAxisLabel);
                    }
                });

                console.log("found statistics");
            }
        });


    }

    // Build metrics dictionary from documentResults
    function generateMetricsDictionary() {
        console.trace("Call stack for generateMetricsDictionary:");
        Object.entries(documentResults).forEach(([filename, fileData]) => {
            if (fileData.metrics) {
                Object.entries(fileData.metrics).forEach(([metricKey, metricValue]) => {
                    const extracted = extractMetricData(filename, metricKey);
                    if (!metricsDictionary[metricKey]) {
                        metricsDictionary[metricKey] = [];
                    }
                    metricsDictionary[metricKey].push(extracted);
                });
            }
        });
        console.log("metricsDictioary:", metricsDictionary);

        createGraphs();
    }



    
});

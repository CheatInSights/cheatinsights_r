// Charts.js - Chart functionality for CheatInSights Dashboard
// Handles all chart creation, data processing, and visualization

console.log('Charts.js loaded successfully');

let metricsDictionary = {};

// Helper: Extract metric data from document results
function extractMetricData(filename, metric) {
    console.log('extractMetricData called with:', filename, metric);
    if (window.documentResults.hasOwnProperty(filename)) {
        return { [filename]: window.documentResults[filename].metrics[metric] };
    }
    return {};
}

// Helper: Extract two specific statistics values from all documents
function getStatisticsXY(statKey1, statKey2) {
    console.log('getStatisticsXY called with:', statKey1, statKey2);
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
    console.log('getStatisticsX called with:', statKey);
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
    console.log('processMetricData called with:', metricData, normalised, count);
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
    console.log('createScatterPlot called with:', dataPoints, isNormalised, metricLabel);
    const graphContainer = document.getElementById('graphContainer');
    if (!graphContainer) {
        console.error('Graph container not found');
        return;
    }

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

    console.log('Creating Chart.js chart with data:', chartData);
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
    console.log('createGraphs called');
    // Show loading state
    const loadingElement = document.getElementById('graphsLoading');
    const errorElement = document.getElementById('graphsError');
    const graphContainer = document.getElementById('graphContainer');
    
    console.log('Graph container found:', !!graphContainer);
    console.log('Loading element found:', !!loadingElement);
    console.log('Error element found:', !!errorElement);
    
    if (loadingElement) loadingElement.style.display = 'block';
    if (errorElement) errorElement.style.display = 'none';
    
    try {
        // Clear existing charts
        if (graphContainer) {
            graphContainer.innerHTML = '';
        }

        const individual = [
            'total_word_count',        // Keep word count
            'unique_rsid_count'        // Keep RSID count
            // Removed: total_characters_count, total_paragraph_count, total_runs_count
        ]
        const pair = [
            ['total_word_count', 'unique_rsid_count'],    // Most important correlation
            ['total_characters_count', 'total_runs_count'] // Keep one character correlation
            // Removed: 5 other pair combinations
        ]

        console.log('Processing metricsDictionary:', metricsDictionary);
        Object.entries(metricsDictionary).forEach(([metricKey, data]) => {
            console.log('Processing metric:', metricKey, data);
            if (metricKey === 'score') {
                const raw = processMetricData(data, false, true);
                createScatterPlot(raw, true, metricKey);
            }
            if (metricKey === 'total_score') {
                const raw = processMetricData(data, false, true);
                createScatterPlot(raw, true, metricKey);
            }
            if (metricKey === 'statistics') {

                // Create individual statistics charts (X vs Count)
                individual.forEach(statKey => {
                    const statData = getStatisticsX(statKey);
                    if (statData.length > 0) {
                        const processedData = processMetricData(statData, false, true);
                        // const processedDataNormalised = processMetricData(statData, true, true);
                        const chartTitle = `${statKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} Distribution`;
                        const xAxisLabel = statKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        createScatterPlot(processedData, true, chartTitle, xAxisLabel, 'Count');
                        // createScatterPlot(processedDataNormalised, true, chartTitle, xAxisLabel, 'Count');
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
                        createScatterPlot(data, true, chartTitle, xAxisLabel, yAxisLabel);
                    }
                });

                console.log("found statistics");
            }
        });

        // Hide loading state
        if (loadingElement) loadingElement.style.display = 'none';
        
    } catch (error) {
        console.error('Error creating graphs:', error);
        if (loadingElement) loadingElement.style.display = 'none';
        if (errorElement) errorElement.style.display = 'block';
    }
}

// Build metrics dictionary from documentResults
function generateMetricsDictionary() {
    console.log('generateMetricsDictionary called');
    console.log('window.documentResults available:', typeof window.documentResults !== 'undefined');
    console.log('window.documentResults:', window.documentResults);
    
    // Clear existing metrics
    metricsDictionary = {};
    
    if (typeof window.documentResults === 'undefined') {
        console.error('window.documentResults is not defined!');
        return;
    }
    
    Object.entries(window.documentResults).forEach(([filename, fileData]) => {
        console.log('Processing file:', filename, fileData);
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
    console.log("Final metricsDictionary:", metricsDictionary);

    createGraphs();
}

// Clear all charts
function clearCharts() {
    const graphContainer = document.getElementById('graphContainer');
    if (graphContainer) {
        graphContainer.innerHTML = '';
    }
}

// Export functions for use in other files
window.chartsModule = {
    generateMetricsDictionary,
    createGraphs,
    clearCharts,
    createScatterPlot,
    processMetricData,
    calculateStats
};

console.log('Charts module exported:', window.chartsModule); 
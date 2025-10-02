/*
  File: static/js/dashboard.js
  Description: Manages the dynamic functionality of the dashboard, including theme switching,
  data fetching, onboarding, and user-configurable data refresh intervals.
*/

document.addEventListener('DOMContentLoaded', () => {
    'use strict';

    // --- STATE AND CONSTANTS ---
    const state = {
        charts: {},
        updateIntervalId: null,
        renderedDeviceIPs: new Set(),
        timeUpdaterId: null,
    };

    const DOM = {
        htmlEl: document.documentElement,
        statsContainer: document.getElementById('stats-container'),
        avgTempChartContainer: document.getElementById('avgTempChart'),
        deviceListContainer: document.getElementById('device-status-list'),
        perDeviceChartsContainer: document.getElementById('per-device-charts'),
        theme: {
            switcher: document.getElementById('theme-switcher'),
            dropdown: document.getElementById('theme-dropdown'),
            toggleButton: document.getElementById('theme-toggle-button'),
            icon: document.getElementById('theme-icon'),
        },
        updateIntervalSelect: document.getElementById('update-interval-select'),
        timeDisplay: document.getElementById('current-time'),
        onboardingRestartButton: document.getElementById('onboarding-restart-button'),
    };

    // --- ONBOARDING TOUR ---
    const initializeOnboardingTour = (force = false) => {
        // Run tour only on the first visit or if forced
        if (!force && localStorage.getItem('dashboardOnboardingComplete') === 'true') {
            return;
        }

        if (!window.driver) {
            console.error('Driver.js library not found.');
            return;
        }

        const driver = window.driver.js.driver;
        const driverObj = driver({
            showProgress: true,
            steps: [
                { 
                    element: '.header h1', 
                    popover: { 
                        title: 'Добро пожаловать!', 
                        description: 'Это панель управления для мониторинга устройств. Этот краткий тур поможет вам освоиться с основными функциями.' 
                    } 
                },
                { 
                    element: '.header-actions', 
                    popover: { 
                        title: 'Элементы управления', 
                        description: 'Здесь находятся глобальные настройки: перезапуск этого обучения, доступ к документации, выбор частоты обновления данных и смена визуальной темы.',
                        side: 'bottom',
                        align: 'end'
                    } 
                },
                { 
                    element: '#stats-container', 
                    popover: { 
                        title: 'Ключевые показатели', 
                        description: 'Эти карточки предоставляют быстрый обзор состояния системы и ее активности.' 
                    } 
                },
                { 
                    element: '#avg-temp-card', 
                    popover: { 
                        title: 'Работа с графиками', 
                        description: 'Графики интерактивны. Попробуйте следующее:<br><br>• <b>Наведите курсор</b> на линию, чтобы увидеть точное значение.<br>• <b>Зажмите ЛКМ и выделите</b> область для ее увеличения.<br>• Используйте <b>колесо мыши</b> для масштабирования. <br><br><i>Для сброса масштаба появится иконка "домика" в правом верхнем углу графика.</i>'
                    } 
                },
                { 
                    element: '#device-list-card', 
                    popover: { 
                        title: 'Список устройств', 
                        description: 'Отслеживайте статус каждого отдельного устройства. Цветной индикатор показывает, находится ли оно в сети.' 
                    } 
                },
                { 
                    element: '#per-device-charts', 
                    popover: { 
                        title: 'Детальные графики', 
                        description: 'Здесь показаны индивидуальные графики для каждого устройства. Все способы взаимодействия, которые вы только что изучили, работают и здесь.',
                        side: 'top',
                        align: 'start'
                    } 
                }
            ],
            nextBtnText: 'Далее',
            prevBtnText: 'Назад',
            doneBtnText: 'Понятно',
            onDestroyed: () => {
                localStorage.setItem('dashboardOnboardingComplete', 'true');
            }
        });

        driverObj.drive();
    };

    // --- CHART CONFIGURATION ---
    const getBaseChartOptions = () => ({
        chart: {
            background: 'transparent',
            toolbar: { show: false },
            parentHeightOffset: 0,
            animations: {
                enabled: true,
                easing: 'easeinout',
                speed: 800,
                dynamicAnimation: { speed: 400 },
            },
        },
        stroke: { curve: 'smooth', width: 3 },
        markers: { size: 0 },
        grid: { show: false },
        xaxis: {
            labels: { show: false },
            axisBorder: { show: false },
            axisTicks: { show: false },
            tooltip: { enabled: false },
        },
        yaxis: {
            labels: { show: false },
        },
        tooltip: {
            enabled: true,
            theme: DOM.htmlEl.getAttribute('data-theme') === 'dark' ? 'dark' : 'light',
            x: { format: 'HH:mm:ss' },
        },
        legend: { show: false },
        noData: {
            text: 'Загрузка данных...',
            style: {
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-sans)',
            },
        },
    });

    // --- UI HELPERS ---
    const initializeClock = () => {
        const updateTime = () => {
            if (DOM.timeDisplay) {
                const now = new Date();
                DOM.timeDisplay.textContent = now.toLocaleTimeString('ru-RU', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        };
        updateTime();
        if (state.timeUpdaterId) clearInterval(state.timeUpdaterId);
        state.timeUpdaterId = setInterval(updateTime, 1000);
    };

    // --- THEME MANAGEMENT ---
    const updateThemeIcon = (preference) => {
        if (!DOM.theme.icon) return;
        const icons = { dark: 'dark_mode', light: 'light_mode', auto: 'brightness_auto' };
        DOM.theme.icon.textContent = icons[preference] || icons.auto;
    };

    const applyTheme = (theme, preference) => {
        DOM.htmlEl.setAttribute('data-theme', theme);
        updateThemeIcon(preference);
        Object.values(state.charts).forEach(chart => {
            if (chart) chart.updateOptions({ tooltip: { theme: theme } });
        });
    };

    const handleThemeSelection = (preference) => {
        if (preference === 'auto') {
            localStorage.removeItem('adminTheme');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            applyTheme(prefersDark ? 'dark' : 'light', 'auto');
        } else {
            localStorage.setItem('adminTheme', preference);
            applyTheme(preference, preference);
        }
    };
    
    const initializeTheme = () => {
        const storedTheme = localStorage.getItem('adminTheme');
        updateThemeIcon(storedTheme || 'auto');
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
            if (!localStorage.getItem('adminTheme')) handleThemeSelection('auto');
        });
        if (DOM.theme.toggleButton) {
            DOM.theme.toggleButton.addEventListener('click', () => DOM.theme.dropdown.classList.toggle('show'));
            document.addEventListener('click', (e) => {
                if (!DOM.theme.switcher.contains(e.target)) DOM.theme.dropdown.classList.remove('show');
            });
            DOM.theme.dropdown.addEventListener('click', (e) => {
                e.preventDefault();
                const target = e.target.closest('[data-theme-preference]');
                if (target) {
                    handleThemeSelection(target.getAttribute('data-theme-preference'));
                    DOM.theme.dropdown.classList.remove('show');
                }
            });
        }
    };
    
    // --- DATA REFRESH INTERVAL CONTROL ---
    const resetUpdateCycle = (intervalMs) => {
        if (state.updateIntervalId) clearInterval(state.updateIntervalId);
        updateDashboard();
        if (intervalMs > 0) state.updateIntervalId = setInterval(updateDashboard, intervalMs);
    };

    const initializeUpdateIntervalControl = () => {
        if (!DOM.updateIntervalSelect) return;
        const savedInterval = localStorage.getItem('dashboardUpdateInterval') || '30000';
        DOM.updateIntervalSelect.value = savedInterval;
        DOM.updateIntervalSelect.addEventListener('change', (e) => {
            const newInterval = parseInt(e.target.value, 10);
            localStorage.setItem('dashboardUpdateInterval', newInterval);
            resetUpdateCycle(newInterval);
        });
        resetUpdateCycle(parseInt(savedInterval, 10));
    };

    // --- RENDER & UPDATE FUNCTIONS ---
    const renderError = (container, message) => {
        if (container) container.innerHTML = `<div class="card col-span-full" style="text-align: center; color: var(--color-red-text);">${message}</div>`;
    };
    
    const renderStats = (stats) => {
        if (!DOM.statsContainer) return;
        const statsMap = [
            { id: 'total_devices', title: 'Всего устройств' },
            { id: 'active_devices', title: 'Активных устройств' },
            { id: 'readings_last_24h', title: 'Показаний (24ч)' },
            { id: 'recent_dos_ip', title: 'Последний Throttled IP' },
        ];
        DOM.statsContainer.innerHTML = statsMap.map(s => {
            const value = stats[s.id];
            const displayValue = typeof value === 'number' ? value.toLocaleString('ru-RU') : (value || 'Нет');
            const valueClass = s.id === 'recent_dos_ip' ? 'stat-ip' : '';
            return `<div class="card"><div class="stats-card-content"><p>${s.title}</p><p class="stat-value ${valueClass}">${displayValue}</p></div></div>`;
        }).join('');
    };

    const renderAvgTempChart = (chartData) => {
        const containerId = 'avgTempChart';
        if (!DOM.avgTempChartContainer) return;
        const seriesData = chartData.labels.map((label, index) => ({ x: new Date(label).getTime(), y: chartData.data[index] }));
        const options = {
            ...getBaseChartOptions(),
            series: [{ name: 'Средняя t (°C)', data: seriesData }],
            chart: { 
                ...getBaseChartOptions().chart, 
                type: 'line',
                zoom: {
                    type: 'x',
                    enabled: true,
                    autoScaleYaxis: true
                },
                toolbar: {
                    autoSelected: 'zoom',
                    show: true,
                    tools: {
                        download: false,
                        selection: true,
                        zoom: false,
                        zoomin: false,
                        zoomout: false,
                        pan: true,
                        reset: true
                    }
                }
            },
            colors: ['var(--chart-line-color-2)'],
        };
        if (!state.charts[containerId]) {
            state.charts[containerId] = new ApexCharts(DOM.avgTempChartContainer, options);
            state.charts[containerId].render();
        }
    };
    
    const updateAvgTempChartData = (chartData) => {
        const chart = state.charts['avgTempChart'];
        if (chart) {
            const seriesData = chartData.labels.map((label, index) => ({ x: new Date(label).getTime(), y: chartData.data[index] }));
            chart.updateSeries([{ data: seriesData }]);
        }
    };

    const renderDeviceList = (devices) => {
        if (!DOM.deviceListContainer) return;
        if (devices.length === 0) {
            DOM.deviceListContainer.innerHTML = `<p style="padding: 1rem; text-align: center;">Устройства не найдены.</p>`;
            return;
        }
        const statusMap = {
            active: { class: 'status-active', label: 'Активен' },
            warning: { class: 'status-warning', label: 'Предупреждение' },
            inactive: { class: 'status-inactive', label: 'Неактивен' },
        };
        DOM.deviceListContainer.innerHTML = devices.map(device => {
            const status = statusMap[device.status] || statusMap.inactive;
            const lastSeen = new Date(device.last_seen).toLocaleString('ru-RU');
            return `<div class="device-item"><div class="device-info"><p class="device-ip">${device.ip_address}</p><p class="device-last-seen">${lastSeen}</p></div><span class="status-badge ${status.class}">${status.label}</span></div>`;
        }).join('');
    };

    const renderDeviceCharts = async (devices) => {
        if (!DOM.perDeviceChartsContainer) return;
        DOM.perDeviceChartsContainer.innerHTML = '';
        Object.keys(state.charts).forEach(key => {
            if (key.startsWith('chart-')) {
                if (state.charts[key]) state.charts[key].destroy();
                delete state.charts[key];
            }
        });
        state.renderedDeviceIPs.clear();
        if (devices.length === 0) return;

        for (const device of devices) {
            const chartId = `chart-${device.ip_address.replace(/\./g, '-')}`;
            const chartWrapper = document.createElement('div');
            chartWrapper.className = 'card';
            chartWrapper.innerHTML = `<h3>Устройство: ${device.ip_address}</h3><div id="${chartId}" class="chart-container"></div>`;
            DOM.perDeviceChartsContainer.appendChild(chartWrapper);
            state.renderedDeviceIPs.add(device.ip_address);
            const chartEl = document.getElementById(chartId);
            const options = {
                ...getBaseChartOptions(),
                series: [],
                chart: { ...getBaseChartOptions().chart, type: 'line' },
                colors: ['var(--chart-line-color-1)', 'var(--chart-line-color-2)'],
            };
            state.charts[chartId] = new ApexCharts(chartEl, options);
            state.charts[chartId].render();
            updateDeviceChartData(device.ip_address);
        }
    };
    
    const updateDeviceChartData = async (ipAddress) => {
        const chartId = `chart-${ipAddress.replace(/\./g, '-')}`;
        const chart = state.charts[chartId];
        if (!chart) return;
        try {
            const response = await fetch(`/api/sensor/device/${ipAddress}/readings/`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            const contactData = data.map(r => [new Date(r.timestamp).getTime(), r.contact_temp]).filter(d => d[1] !== null);
            const nonContactData = data.map(r => [new Date(r.timestamp).getTime(), r.non_contact_temp]).filter(d => d[1] !== null);
            chart.updateSeries([
                { name: 'Контактная t (°C)', data: contactData },
                { name: 'Бесконтактная t (°C)', data: nonContactData }
            ]);
        } catch (error) {
            console.error(`Error updating chart data for ${ipAddress}:`, error);
        }
    };

    // --- MAIN DATA FETCH AND UPDATE ---
    let isFirstLoad = true;
    async function updateDashboard() {
        try {
            const response = await fetch('/api/dashboard/');
            if (!response.ok) throw new Error(`Ошибка сети: ${response.statusText}`);
            const data = await response.json();
            renderStats(data.statistics);
            renderDeviceList(data.devices);
            if (isFirstLoad) {
                renderAvgTempChart(data.system_average_temperature_chart);
                await renderDeviceCharts(data.devices);
                isFirstLoad = false;
                // Wait a moment for the DOM to settle before starting the tour
                setTimeout(() => initializeOnboardingTour(false), 500);
            } else {
                updateAvgTempChartData(data.system_average_temperature_chart);
                const newDeviceIPs = new Set(data.devices.map(d => d.ip_address));
                if (newDeviceIPs.size !== state.renderedDeviceIPs.size || ![...newDeviceIPs].every(ip => state.renderedDeviceIPs.has(ip))) {
                    await renderDeviceCharts(data.devices);
                } else {
                    for (const device of data.devices) {
                        updateDeviceChartData(device.ip_address);
                    }
                }
            }
        } catch (error)
        {
            console.error('Ошибка при обновлении панели управления:', error);
            if (isFirstLoad) renderError(DOM.statsContainer, 'Не удалось загрузить данные.');
        }
    }

    // --- INITIALIZATION ---
    function init() {
        initializeClock();
        initializeTheme();
        initializeUpdateIntervalControl();

        if (DOM.onboardingRestartButton) {
            DOM.onboardingRestartButton.addEventListener('click', () => initializeOnboardingTour(true));
        }
    }
    init();
});

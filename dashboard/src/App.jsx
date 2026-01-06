const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ============================================
// Configuration
// ============================================
const API_BASE = 'http://localhost:8000/api/v1';

// ============================================
// Icons (inline SVG components)
// ============================================
const Icons = {
    Home: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
    ),
    FileText: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
    ),
    ClipboardCheck: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
        </svg>
    ),
    MessageCircle: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
    ),
    Database: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
        </svg>
    ),
    Upload: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
        </svg>
    ),
    Send: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
    ),
    Search: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
    ),
    AlertTriangle: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
    ),
    CheckCircle: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    ),
    XCircle: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    ),
    Plane: () => (
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
        </svg>
    ),
    RefreshCw: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    ),
    Download: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
    ),
    X: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
    ),
    ChevronRight: () => (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
    ),
    Info: () => (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    ),
};

// ============================================
// Utility Components
// ============================================

// Status Badge
const StatusBadge = ({ status, size = 'md' }) => {
    const config = {
        'COMPLIANT': { bg: 'bg-emerald-600', text: 'text-emerald-100', icon: '✓' },
        'MORE_RESTRICTIVE': { bg: 'bg-green-600', text: 'text-green-100', icon: '✓+' },
        'NON_COMPLIANT': { bg: 'bg-red-600', text: 'text-red-100', icon: '✗' },
        'MISSING_IN_MEL': { bg: 'bg-amber-600', text: 'text-amber-100', icon: '⚠' },
        'EXTRA_IN_MEL': { bg: 'bg-blue-600', text: 'text-blue-100', icon: '+' },
    };
    const c = config[status] || { bg: 'bg-gray-600', text: 'text-gray-100', icon: '?' };
    const sizeClasses = size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm';

    return (
        <span className={`${c.bg} ${c.text} ${sizeClasses} rounded-full font-medium inline-flex items-center gap-1`}>
            <span>{c.icon}</span>
            <span className="hidden sm:inline">{status.replace(/_/g, ' ')}</span>
        </span>
    );
};

// Compliance Gauge
const ComplianceGauge = ({ score }) => {
    const rotation = -90 + (score / 100) * 180;
    const color = score >= 90 ? '#10b981' : score >= 70 ? '#f59e0b' : '#ef4444';

    return (
        <div className="gauge-container">
            <div className="gauge-bg"></div>
            <div className="gauge-inner"></div>
            <div className="gauge-needle" style={{ transform: `rotate(${rotation}deg)` }}></div>
            <div className="gauge-center"></div>
            <div className="absolute bottom-1 left-0 right-0 text-center">
                <span className="text-2xl font-bold" style={{ color }}>{score.toFixed(1)}%</span>
            </div>
        </div>
    );
};

// Stat Card
const StatCard = ({ title, value, icon, color, subtitle }) => {
    const colors = {
        green: 'from-emerald-600/20 to-emerald-600/5 border-emerald-500/30',
        red: 'from-red-600/20 to-red-600/5 border-red-500/30',
        yellow: 'from-amber-600/20 to-amber-600/5 border-amber-500/30',
        blue: 'from-blue-600/20 to-blue-600/5 border-blue-500/30',
        gray: 'from-gray-600/20 to-gray-600/5 border-gray-500/30',
        orange: 'from-orange-600/20 to-orange-600/5 border-orange-500/30',
    };

    return (
        <div className={`rounded-xl bg-gradient-to-br ${colors[color]} border p-4 card-hover`}>
            <div className="flex items-start justify-between">
                <div>
                    <p className="text-gray-400 text-sm font-medium">{title}</p>
                    <p className="text-3xl font-bold mt-1">{value}</p>
                    {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
                </div>
                <span className="text-3xl opacity-50">{icon}</span>
            </div>
        </div>
    );
};

// Loading Spinner
const Spinner = ({ size = 'md' }) => {
    const sizeClasses = { sm: 'w-4 h-4', md: 'w-8 h-8', lg: 'w-12 h-12' };
    return (
        <div className={`${sizeClasses[size]} border-2 border-aviation-cyan border-t-transparent rounded-full animate-spin`}></div>
    );
};

// ============================================
// Navigation Sidebar
// ============================================
const Sidebar = ({ activeTab, setActiveTab, auditData }) => {
    const tabs = [
        { id: 'overview', label: 'Vue d\'ensemble', icon: Icons.Home },
        { id: 'parsing', label: 'Parsing', icon: Icons.FileText },
        { id: 'audit', label: 'Audit', icon: Icons.ClipboardCheck },
        { id: 'chat', label: 'Assistant IA', icon: Icons.MessageCircle },
        { id: 'items', label: 'Items', icon: Icons.Database },
    ];

    return (
        <aside className="w-64 bg-navy-900 border-r border-navy-700 flex flex-col">
            {/* Logo */}
            <div className="p-6 border-b border-navy-700">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-aviation-orange to-aviation-yellow flex items-center justify-center">
                        <span className="text-white text-xl">✈</span>
                    </div>
                    <div>
                        <h1 className="font-bold text-lg">MEL/MMEL</h1>
                        <p className="text-xs text-gray-400">Audit Dashboard</p>
                    </div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-4">
                <ul className="space-y-2">
                    {tabs.map(tab => {
                        const Icon = tab.icon;
                        const isActive = activeTab === tab.id;
                        return (
                            <li key={tab.id}>
                                <button
                                    onClick={() => setActiveTab(tab.id)}
                                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                                        isActive
                                            ? 'bg-aviation-orange text-white shadow-lg shadow-aviation-orange/20'
                                            : 'text-gray-400 hover:bg-navy-800 hover:text-white'
                                    }`}
                                >
                                    <Icon />
                                    <span className="font-medium">{tab.label}</span>
                                    {tab.id === 'audit' && auditData?.summary?.non_compliant > 0 && (
                                        <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                                            {auditData.summary.non_compliant}
                                        </span>
                                    )}
                                </button>
                            </li>
                        );
                    })}
                </ul>
            </nav>

            {/* Aircraft Info */}
            <div className="p-4 border-t border-navy-700">
                <div className="bg-navy-800 rounded-lg p-4">
                    <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Aéronef</p>
                    <p className="font-mono font-bold text-lg">PC-12</p>
                    <p className="text-aviation-cyan font-mono">HB-FVT</p>
                    <p className="text-xs text-gray-500 mt-2">AMAC Corporate Jet</p>
                </div>
            </div>
        </aside>
    );
};

// ============================================
// Overview Tab
// ============================================
const OverviewTab = ({ mmelData, melData, auditData, onNavigate }) => {
    const summary = auditData?.summary || {};

    return (
        <div className="tab-content space-y-6">
            {/* Header with Gauge */}
            <div className="bg-navy-800 rounded-2xl p-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold">Score de Conformité</h2>
                        <p className="text-gray-400 mt-1">MEL vs MMEL - Pilatus PC-12 HB-FVT</p>
                    </div>
                    <ComplianceGauge score={summary.compliance_score || 0} />
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard title="Items MMEL" value={mmelData?.metadata?.total_items || 0} icon="📘" color="gray" />
                <StatCard title="Items MEL" value={melData?.metadata?.total_items || 0} icon="📗" color="gray" />
                <StatCard title="Conformes" value={(summary.compliant || 0) + (summary.more_restrictive || 0)} icon="✓" color="green" />
                <StatCard title="Non Conformes" value={summary.non_compliant || 0} icon="✗" color="red" />
            </div>

            {/* Quick Actions */}
            <div className="grid md:grid-cols-3 gap-4">
                <button
                    onClick={() => onNavigate('audit')}
                    className="bg-navy-800 hover:bg-navy-700 rounded-xl p-6 text-left transition-all card-hover group"
                >
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-lg bg-red-600/20 flex items-center justify-center">
                            <Icons.AlertTriangle />
                        </div>
                        <div>
                            <h3 className="font-semibold group-hover:text-aviation-orange transition-colors">
                                {summary.non_compliant || 0} Non-Conformités
                            </h3>
                            <p className="text-sm text-gray-400">Voir les détails</p>
                        </div>
                        <Icons.ChevronRight />
                    </div>
                </button>

                <button
                    onClick={() => onNavigate('chat')}
                    className="bg-navy-800 hover:bg-navy-700 rounded-xl p-6 text-left transition-all card-hover group"
                >
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-lg bg-aviation-cyan/20 flex items-center justify-center">
                            <Icons.MessageCircle />
                        </div>
                        <div>
                            <h3 className="font-semibold group-hover:text-aviation-orange transition-colors">
                                Assistant IA
                            </h3>
                            <p className="text-sm text-gray-400">Poser une question</p>
                        </div>
                        <Icons.ChevronRight />
                    </div>
                </button>

                <button
                    onClick={() => onNavigate('items')}
                    className="bg-navy-800 hover:bg-navy-700 rounded-xl p-6 text-left transition-all card-hover group"
                >
                    <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-lg bg-amber-600/20 flex items-center justify-center">
                            <Icons.Database />
                        </div>
                        <div>
                            <h3 className="font-semibold group-hover:text-aviation-orange transition-colors">
                                {summary.missing_in_mel || 0} Manquants
                            </h3>
                            <p className="text-sm text-gray-400">Items MMEL absents de MEL</p>
                        </div>
                        <Icons.ChevronRight />
                    </div>
                </button>
            </div>

            {/* Status Distribution */}
            <div className="bg-navy-800 rounded-2xl p-6">
                <h3 className="font-semibold mb-4">Distribution des Statuts</h3>
                <div className="space-y-3">
                    {[
                        { label: 'Conformes', value: summary.compliant || 0, color: 'bg-emerald-500', total: summary.total_compared || 1 },
                        { label: 'Plus Restrictifs', value: summary.more_restrictive || 0, color: 'bg-green-500', total: summary.total_compared || 1 },
                        { label: 'Non Conformes', value: summary.non_compliant || 0, color: 'bg-red-500', total: summary.total_compared || 1 },
                        { label: 'Manquants MEL', value: summary.missing_in_mel || 0, color: 'bg-amber-500', total: summary.total_compared || 1 },
                        { label: 'Extra MEL', value: summary.extra_in_mel || 0, color: 'bg-blue-500', total: summary.total_compared || 1 },
                    ].map(item => (
                        <div key={item.label} className="flex items-center gap-4">
                            <span className="w-32 text-sm text-gray-400">{item.label}</span>
                            <div className="flex-1 h-2 bg-navy-700 rounded-full overflow-hidden">
                                <div
                                    className={`h-full ${item.color} transition-all duration-500`}
                                    style={{ width: `${(item.value / item.total) * 100}%` }}
                                ></div>
                            </div>
                            <span className="w-12 text-right font-mono text-sm">{item.value}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

// ============================================
// Parsing Tab
// ============================================
const ParsingTab = ({ onRefresh }) => {
    const [parsing, setParsing] = useState(false);
    const [logs, setLogs] = useState([]);
    const [files, setFiles] = useState({ mmel: null, mel: null });

    const addLog = (message, type = 'info') => {
        setLogs(prev => [...prev, { message, type, time: new Date().toLocaleTimeString() }]);
    };

    const handleParse = async (type) => {
        setParsing(true);
        addLog(`Démarrage du parsing ${type.toUpperCase()}...`, 'info');

        try {
            const response = await fetch(`${API_BASE}/parse/${type}`, { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                addLog(`✓ ${type.toUpperCase()} parsé avec succès: ${data.total_items || '?'} items`, 'success');
                onRefresh?.();
            } else {
                addLog(`✗ Erreur: ${data.detail || 'Erreur inconnue'}`, 'error');
            }
        } catch (error) {
            addLog(`✗ Erreur réseau: ${error.message}`, 'error');
        }

        setParsing(false);
    };

    const handleRunAudit = async () => {
        setParsing(true);
        addLog('Lancement de l\'audit MEL vs MMEL...', 'info');

        try {
            const response = await fetch(`${API_BASE}/audit/quick`, { method: 'POST' });
            const data = await response.json();

            if (response.ok) {
                addLog(`✓ Audit terminé - Score: ${data.summary?.compliance_score?.toFixed(1)}%`, 'success');
                onRefresh?.();
            } else {
                addLog(`✗ Erreur: ${data.detail || 'Erreur inconnue'}`, 'error');
            }
        } catch (error) {
            addLog(`✗ Erreur réseau: ${error.message}`, 'error');
        }

        setParsing(false);
    };

    return (
        <div className="tab-content space-y-6">
            <div className="bg-navy-800 rounded-2xl p-6">
                <h2 className="text-xl font-bold mb-6">Parsing des Documents</h2>

                <div className="grid md:grid-cols-2 gap-6">
                    {/* MMEL Card */}
                    <div className="bg-navy-900 rounded-xl p-6 border border-navy-700">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-orange-600/20 flex items-center justify-center">
                                <span className="text-xl">📘</span>
                            </div>
                            <div>
                                <h3 className="font-semibold">MMEL</h3>
                                <p className="text-xs text-gray-400">Master Minimum Equipment List</p>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="bg-navy-800 rounded-lg p-3">
                                <p className="text-xs text-gray-500">Fichier source</p>
                                <p className="font-mono text-sm truncate">mmel_pc12_raw.md</p>
                            </div>

                            <button
                                onClick={() => handleParse('mmel')}
                                disabled={parsing}
                                className="w-full bg-aviation-orange hover:bg-aviation-orange/80 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                            >
                                {parsing ? <Spinner size="sm" /> : <Icons.RefreshCw />}
                                Parser MMEL
                            </button>
                        </div>
                    </div>

                    {/* MEL Card */}
                    <div className="bg-navy-900 rounded-xl p-6 border border-navy-700">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-lg bg-blue-600/20 flex items-center justify-center">
                                <span className="text-xl">📗</span>
                            </div>
                            <div>
                                <h3 className="font-semibold">MEL</h3>
                                <p className="text-xs text-gray-400">Minimum Equipment List (Opérateur)</p>
                            </div>
                        </div>

                        <div className="space-y-3">
                            <div className="bg-navy-800 rounded-lg p-3">
                                <p className="text-xs text-gray-500">Fichier source</p>
                                <p className="font-mono text-sm truncate">mel_pc12_raw.md</p>
                            </div>

                            <button
                                onClick={() => handleParse('mel')}
                                disabled={parsing}
                                className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors flex items-center justify-center gap-2"
                            >
                                {parsing ? <Spinner size="sm" /> : <Icons.RefreshCw />}
                                Parser MEL
                            </button>
                        </div>
                    </div>
                </div>

                {/* Run Audit Button */}
                <div className="mt-6 pt-6 border-t border-navy-700">
                    <button
                        onClick={handleRunAudit}
                        disabled={parsing}
                        className="w-full bg-gradient-to-r from-emerald-600 to-aviation-cyan hover:from-emerald-500 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold py-4 px-6 rounded-xl transition-all flex items-center justify-center gap-3"
                    >
                        {parsing ? <Spinner size="sm" /> : <Icons.ClipboardCheck />}
                        Lancer l'Audit MEL vs MMEL
                    </button>
                </div>
            </div>

            {/* Logs */}
            {logs.length > 0 && (
                <div className="bg-navy-800 rounded-2xl p-6">
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="font-semibold">Logs</h3>
                        <button onClick={() => setLogs([])} className="text-sm text-gray-400 hover:text-white">
                            Effacer
                        </button>
                    </div>
                    <div className="bg-navy-950 rounded-lg p-4 font-mono text-sm max-h-64 overflow-y-auto space-y-1">
                        {logs.map((log, i) => (
                            <div key={i} className={`flex gap-3 ${
                                log.type === 'error' ? 'text-red-400' :
                                log.type === 'success' ? 'text-emerald-400' : 'text-gray-400'
                            }`}>
                                <span className="text-gray-600">[{log.time}]</span>
                                <span>{log.message}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

// ============================================
// Audit Tab
// ============================================
const AuditTab = ({ auditData, onItemClick }) => {
    const [filter, setFilter] = useState('ALL');
    const [search, setSearch] = useState('');

    const results = auditData?.results || [];
    const summary = auditData?.summary || {};

    const filteredResults = useMemo(() => {
        return results.filter(item => {
            if (filter !== 'ALL' && item.status !== filter) return false;
            if (search) {
                const q = search.toLowerCase();
                const code = (item.item_code || '').toLowerCase();
                const title = (item.mel_data?.itemTitle || item.mmel_data?.itemTitle || '').toLowerCase();
                if (!code.includes(q) && !title.includes(q)) return false;
            }
            return true;
        });
    }, [results, filter, search]);

    const statusCounts = useMemo(() => {
        const counts = { ALL: results.length };
        results.forEach(r => {
            counts[r.status] = (counts[r.status] || 0) + 1;
        });
        return counts;
    }, [results]);

    return (
        <div className="tab-content space-y-6">
            {/* Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <StatCard title="Conformes" value={summary.compliant || 0} icon="✓" color="green" />
                <StatCard title="Plus Restrictifs" value={summary.more_restrictive || 0} icon="✓+" color="green" />
                <StatCard title="Non Conformes" value={summary.non_compliant || 0} icon="✗" color="red" />
                <StatCard title="Manquants" value={summary.missing_in_mel || 0} icon="⚠" color="yellow" />
                <StatCard title="Extra" value={summary.extra_in_mel || 0} icon="+" color="blue" />
            </div>

            {/* Filters */}
            <div className="bg-navy-800 rounded-xl p-4">
                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex-1 min-w-[200px]">
                        <div className="relative">
                            <Icons.Search />
                            <input
                                type="text"
                                placeholder="Rechercher par code ou titre..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                className="w-full bg-navy-900 border border-navy-700 rounded-lg pl-10 pr-4 py-2 text-sm focus:outline-none focus:border-aviation-cyan"
                            />
                        </div>
                    </div>

                    <div className="flex gap-2 flex-wrap">
                        {['ALL', 'COMPLIANT', 'MORE_RESTRICTIVE', 'NON_COMPLIANT', 'MISSING_IN_MEL', 'EXTRA_IN_MEL'].map(status => (
                            <button
                                key={status}
                                onClick={() => setFilter(status)}
                                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                                    filter === status
                                        ? 'bg-aviation-orange text-white'
                                        : 'bg-navy-700 text-gray-300 hover:bg-navy-600'
                                }`}
                            >
                                {status === 'ALL' ? 'Tous' : status.replace(/_/g, ' ')}
                                <span className="ml-1 opacity-60">({statusCounts[status] || 0})</span>
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Results Table */}
            <div className="bg-navy-800 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead className="bg-navy-900">
                            <tr>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">Code</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">Titre</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">ATA</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">Statut</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">MEL</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-400">MMEL</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredResults.slice(0, 100).map((item, idx) => (
                                <tr
                                    key={item.item_code || idx}
                                    onClick={() => onItemClick?.(item)}
                                    className={`border-t border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors ${
                                        item.status === 'NON_COMPLIANT' ? 'bg-red-900/10' : ''
                                    }`}
                                >
                                    <td className="py-3 px-4 font-mono font-medium">{item.item_code}</td>
                                    <td className="py-3 px-4 max-w-xs truncate">
                                        {item.mel_data?.itemTitle || item.mmel_data?.itemTitle || '-'}
                                    </td>
                                    <td className="py-3 px-4">
                                        {item.mel_data?.ataChapter || item.mmel_data?.ataChapter || '-'}
                                    </td>
                                    <td className="py-3 px-4">
                                        <StatusBadge status={item.status} size="sm" />
                                    </td>
                                    <td className="py-3 px-4 font-mono">
                                        {item.details?.mel_interval || item.mel_data?.category || '-'}
                                    </td>
                                    <td className="py-3 px-4 font-mono">
                                        {item.details?.mmel_interval || item.mmel_data?.rectificationInterval || '-'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {filteredResults.length === 0 && (
                    <div className="text-center py-12 text-gray-500">
                        Aucun résultat ne correspond à vos filtres
                    </div>
                )}

                {filteredResults.length > 100 && (
                    <div className="text-center py-4 text-gray-500 border-t border-navy-700">
                        Affichage des 100 premiers résultats sur {filteredResults.length}
                    </div>
                )}
            </div>
        </div>
    );
};

// ============================================
// Chat Tab
// ============================================
const ChatTab = () => {
    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: 'Bonjour ! Je suis votre assistant MEL/MMEL. Je peux vous aider avec :\n\n• **Dispatch** : Vérifier si un item permet le dispatch\n• **Comparaison** : Comparer MEL vs MMEL\n• **Explication** : Détailler un item spécifique\n• **Audit** : Analyser les non-conformités\n\nPosez-moi votre question !',
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const messagesEndRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setLoading(true);

        try {
            // Determine endpoint based on message content
            let endpoint = '/chat';
            let body = { question: userMessage };

            const lower = userMessage.toLowerCase();
            if (lower.includes('dispatch') || lower.includes('go/no-go')) {
                const codeMatch = userMessage.match(/\d{2}-\d{2}-\d{2}[A-Z]?/);
                if (codeMatch) {
                    endpoint = '/chat/dispatch';
                    body = { item_code: codeMatch[0] };
                }
            } else if (lower.includes('compare') || lower.includes('comparer')) {
                const codeMatch = userMessage.match(/\d{2}-\d{2}-\d{2}[A-Z]?/);
                if (codeMatch) {
                    endpoint = '/chat/compare';
                    body = { item_code: codeMatch[0] };
                }
            } else if (lower.includes('explain') || lower.includes('expliquer')) {
                const codeMatch = userMessage.match(/\d{2}-\d{2}-\d{2}[A-Z]?/);
                if (codeMatch) {
                    endpoint = '/chat/explain';
                    body = { item_code: codeMatch[0] };
                }
            }

            const response = await fetch(`${API_BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            const data = await response.json();

            if (response.ok) {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: data.response || data.answer || data.message || 'Réponse reçue.',
                }]);
            } else {
                setMessages(prev => [...prev, {
                    role: 'assistant',
                    content: `❌ Erreur: ${data.detail || 'Une erreur est survenue.'}`,
                }]);
            }
        } catch (error) {
            setMessages(prev => [...prev, {
                role: 'assistant',
                content: `❌ Erreur réseau: ${error.message}`,
            }]);
        }

        setLoading(false);
    };

    const quickActions = [
        { label: 'Dispatch 21-30-02D', query: 'Est-ce que je peux dispatch avec 21-30-02D inopérant ?' },
        { label: 'Non-conformités', query: 'Quelles sont les non-conformités critiques ?' },
        { label: 'Comparer 34-20-01A', query: 'Compare 34-20-01A entre MEL et MMEL' },
    ];

    return (
        <div className="tab-content h-[calc(100vh-8rem)] flex flex-col">
            {/* Chat Messages */}
            <div className="flex-1 bg-navy-800 rounded-2xl p-4 overflow-y-auto mb-4">
                <div className="space-y-4">
                    {messages.map((msg, idx) => (
                        <div
                            key={idx}
                            className={`chat-message flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                                msg.role === 'user'
                                    ? 'bg-aviation-orange text-white'
                                    : 'bg-navy-700 text-gray-100'
                            }`}>
                                <div className="whitespace-pre-wrap text-sm" dangerouslySetInnerHTML={{
                                    __html: msg.content
                                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                        .replace(/\n/g, '<br/>')
                                }} />
                            </div>
                        </div>
                    ))}

                    {loading && (
                        <div className="chat-message flex justify-start">
                            <div className="bg-navy-700 rounded-2xl px-4 py-3">
                                <div className="typing-indicator flex gap-1">
                                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                                    <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                                </div>
                            </div>
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Quick Actions */}
            <div className="flex gap-2 mb-4 flex-wrap">
                {quickActions.map((action, idx) => (
                    <button
                        key={idx}
                        onClick={() => setInput(action.query)}
                        className="bg-navy-700 hover:bg-navy-600 text-sm px-3 py-1.5 rounded-lg transition-colors"
                    >
                        {action.label}
                    </button>
                ))}
            </div>

            {/* Input */}
            <form onSubmit={sendMessage} className="flex gap-3">
                <input
                    type="text"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    placeholder="Posez votre question sur MEL/MMEL..."
                    className="flex-1 bg-navy-800 border border-navy-700 rounded-xl px-4 py-3 focus:outline-none focus:border-aviation-cyan"
                    disabled={loading}
                />
                <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="bg-aviation-orange hover:bg-aviation-orange/80 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl transition-colors flex items-center gap-2"
                >
                    <Icons.Send />
                </button>
            </form>
        </div>
    );
};

// ============================================
// Items Tab
// ============================================
const ItemsTab = ({ mmelData, melData }) => {
    const [source, setSource] = useState('mmel');
    const [search, setSearch] = useState('');
    const [ataFilter, setAtaFilter] = useState('ALL');

    const items = source === 'mmel' ? (mmelData?.items || []) : (melData?.items || []);

    const ataChapters = useMemo(() => {
        const chapters = new Set();
        items.forEach(item => {
            if (item.ataChapter) chapters.add(item.ataChapter);
        });
        return Array.from(chapters).sort((a, b) => parseInt(a) - parseInt(b));
    }, [items]);

    const filteredItems = useMemo(() => {
        return items.filter(item => {
            if (ataFilter !== 'ALL' && item.ataChapter !== ataFilter) return false;
            if (search) {
                const q = search.toLowerCase();
                const code = (item.fullItemCode || '').toLowerCase();
                const title = (item.itemTitle || '').toLowerCase();
                if (!code.includes(q) && !title.includes(q)) return false;
            }
            return true;
        });
    }, [items, ataFilter, search]);

    return (
        <div className="tab-content space-y-6">
            {/* Source Toggle */}
            <div className="flex items-center gap-4">
                <div className="bg-navy-800 rounded-xl p-1 inline-flex">
                    <button
                        onClick={() => setSource('mmel')}
                        className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                            source === 'mmel'
                                ? 'bg-aviation-orange text-white'
                                : 'text-gray-400 hover:text-white'
                        }`}
                    >
                        MMEL ({mmelData?.items?.length || 0})
                    </button>
                    <button
                        onClick={() => setSource('mel')}
                        className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                            source === 'mel'
                                ? 'bg-blue-600 text-white'
                                : 'text-gray-400 hover:text-white'
                        }`}
                    >
                        MEL ({melData?.items?.length || 0})
                    </button>
                </div>

                <div className="flex-1 relative">
                    <Icons.Search />
                    <input
                        type="text"
                        placeholder="Rechercher..."
                        value={search}
                        onChange={e => setSearch(e.target.value)}
                        className="w-full bg-navy-800 border border-navy-700 rounded-xl pl-10 pr-4 py-2 focus:outline-none focus:border-aviation-cyan"
                    />
                </div>

                <select
                    value={ataFilter}
                    onChange={e => setAtaFilter(e.target.value)}
                    className="bg-navy-800 border border-navy-700 rounded-xl px-4 py-2 focus:outline-none focus:border-aviation-cyan"
                >
                    <option value="ALL">Tous les chapitres ATA</option>
                    {ataChapters.map(ata => (
                        <option key={ata} value={ata}>ATA {ata}</option>
                    ))}
                </select>
            </div>

            {/* Items Grid */}
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredItems.slice(0, 50).map((item, idx) => (
                    <div
                        key={item.fullItemCode || idx}
                        className="bg-navy-800 rounded-xl p-4 border border-navy-700 hover:border-aviation-cyan/50 transition-colors card-hover"
                    >
                        <div className="flex items-start justify-between mb-2">
                            <span className="font-mono font-bold text-aviation-cyan">{item.fullItemCode}</span>
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                                item.category === 'A' || item.rectificationInterval === 'A' ? 'bg-red-600/30 text-red-300' :
                                item.category === 'B' || item.rectificationInterval === 'B' ? 'bg-orange-600/30 text-orange-300' :
                                item.category === 'C' || item.rectificationInterval === 'C' ? 'bg-yellow-600/30 text-yellow-300' :
                                'bg-green-600/30 text-green-300'
                            }`}>
                                Cat. {item.category || item.rectificationInterval || '?'}
                            </span>
                        </div>

                        <p className="text-sm text-gray-300 mb-3 line-clamp-2">{item.itemTitle}</p>

                        <div className="flex items-center gap-4 text-xs text-gray-500">
                            <span>ATA {item.ataChapter}</span>
                            <span>Inst: {item.numberInstalled}</span>
                            <span>Req: {item.numberRequired}</span>
                            {item.requiresMaintenance && <span className="text-amber-400">(M)</span>}
                            {item.requiresOperations && <span className="text-blue-400">(O)</span>}
                        </div>
                    </div>
                ))}
            </div>

            {filteredItems.length > 50 && (
                <div className="text-center text-gray-500">
                    Affichage des 50 premiers items sur {filteredItems.length}
                </div>
            )}
        </div>
    );
};

// ============================================
// Item Detail Modal
// ============================================
const ItemDetailModal = ({ item, onClose }) => {
    if (!item) return null;

    const mel = item.mel_data || {};
    const mmel = item.mmel_data || {};

    return (
        <div className="fixed inset-0 bg-black/70 modal-backdrop flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-navy-800 rounded-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="bg-navy-900 px-6 py-4 flex items-center justify-between border-b border-navy-700">
                    <div>
                        <h3 className="text-xl font-bold font-mono">{item.item_code}</h3>
                        <p className="text-gray-400">{mel.itemTitle || mmel.itemTitle}</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <StatusBadge status={item.status} />
                        <button onClick={onClose} className="text-gray-400 hover:text-white p-2">
                            <Icons.X />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="p-6 overflow-y-auto max-h-[70vh]">
                    {/* Issues */}
                    {item.issues?.length > 0 && (
                        <div className="mb-6 bg-red-900/20 border border-red-800 rounded-xl p-4">
                            <h4 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
                                <Icons.AlertTriangle />
                                Problèmes Identifiés
                            </h4>
                            {item.issues.map((issue, idx) => (
                                <p key={idx} className="text-red-300 flex items-center gap-2 text-sm">
                                    <span>✗</span> {issue}
                                </p>
                            ))}
                        </div>
                    )}

                    {/* Comparison Table */}
                    <h4 className="font-semibold mb-3 flex items-center gap-2">
                        <Icons.ClipboardCheck />
                        Comparaison MEL vs MMEL
                    </h4>
                    <div className="bg-navy-900 rounded-xl overflow-hidden mb-6">
                        <table className="w-full text-sm">
                            <thead className="bg-navy-950">
                                <tr>
                                    <th className="text-left py-3 px-4 text-gray-400">Champ</th>
                                    <th className="text-left py-3 px-4 text-blue-400">MEL</th>
                                    <th className="text-left py-3 px-4 text-aviation-orange">MMEL</th>
                                </tr>
                            </thead>
                            <tbody>
                                {[
                                    ['Intervalle', mel.category || mel.rectificationInterval || '-', mmel.rectificationInterval || '-'],
                                    ['Installé', mel.numberInstalled || '-', mmel.numberInstalled || '-'],
                                    ['Requis', mel.numberRequired || '-', mmel.numberRequired || '-'],
                                    ['Maintenance (M)', mel.requiresMaintenance ? 'Oui' : 'Non', mmel.requiresMaintenance ? 'Oui' : 'Non'],
                                    ['Opérations (O)', mel.requiresOperations ? 'Oui' : 'Non', mmel.requiresOperations ? 'Oui' : 'Non'],
                                ].map(([label, melVal, mmelVal], idx) => {
                                    const isDiff = melVal !== mmelVal && melVal !== '-' && mmelVal !== '-';
                                    return (
                                        <tr key={idx} className="border-t border-navy-800">
                                            <td className="py-2 px-4 text-gray-400">{label}</td>
                                            <td className={`py-2 px-4 font-mono ${isDiff ? 'text-yellow-400 bg-yellow-900/20' : ''}`}>{melVal}</td>
                                            <td className={`py-2 px-4 font-mono ${isDiff ? 'text-yellow-400 bg-yellow-900/20' : ''}`}>{mmelVal}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>

                    {/* Remarks */}
                    <div className="grid md:grid-cols-2 gap-4">
                        <div>
                            <h4 className="text-blue-400 font-semibold mb-2">Remarques MEL</h4>
                            <div className="bg-navy-900 rounded-xl p-4 text-sm">
                                <p>{mel.remarksText || 'Aucune remarque'}</p>
                                {mel.conditions?.length > 0 && (
                                    <ul className="mt-3 space-y-1 text-gray-400">
                                        {mel.conditions.map((c, i) => <li key={i}>{c}</li>)}
                                    </ul>
                                )}
                            </div>
                        </div>
                        <div>
                            <h4 className="text-aviation-orange font-semibold mb-2">Remarques MMEL</h4>
                            <div className="bg-navy-900 rounded-xl p-4 text-sm">
                                <p>{mmel.remarksText || 'Aucune remarque'}</p>
                                {mmel.conditions?.length > 0 && (
                                    <ul className="mt-3 space-y-1 text-gray-400">
                                        {mmel.conditions.map((c, i) => <li key={i}>{c}</li>)}
                                    </ul>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

// ============================================
// Main App Component
// ============================================
const App = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [mmelData, setMmelData] = useState(null);
    const [melData, setMelData] = useState(null);
    const [auditData, setAuditData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [selectedItem, setSelectedItem] = useState(null);

    // Load all data
    const loadData = useCallback(async () => {
        setLoading(true);
        try {
            // Load from local files
            const [mmelRes, melRes, auditRes] = await Promise.all([
                fetch('data/mmel_pc12_structured.json').catch(() => null),
                fetch('data/mel_pc12_structured.json').catch(() => null),
                fetch('data/audit_report.json').catch(() => null),
            ]);

            if (mmelRes?.ok) setMmelData(await mmelRes.json());
            if (melRes?.ok) setMelData(await melRes.json());
            if (auditRes?.ok) setAuditData(await auditRes.json());
        } catch (error) {
            console.error('Error loading data:', error);
        }
        setLoading(false);
    }, []);

    useEffect(() => {
        loadData();
    }, [loadData]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-navy-950">
                <div className="text-center">
                    <Spinner size="lg" />
                    <p className="mt-4 text-gray-400">Chargement des données...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen bg-navy-950">
            {/* Sidebar */}
            <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} auditData={auditData} />

            {/* Main Content */}
            <main className="flex-1 p-6 overflow-y-auto">
                <div className="max-w-7xl mx-auto">
                    {activeTab === 'overview' && (
                        <OverviewTab
                            mmelData={mmelData}
                            melData={melData}
                            auditData={auditData}
                            onNavigate={setActiveTab}
                        />
                    )}
                    {activeTab === 'parsing' && (
                        <ParsingTab onRefresh={loadData} />
                    )}
                    {activeTab === 'audit' && (
                        <AuditTab auditData={auditData} onItemClick={setSelectedItem} />
                    )}
                    {activeTab === 'chat' && (
                        <ChatTab />
                    )}
                    {activeTab === 'items' && (
                        <ItemsTab mmelData={mmelData} melData={melData} />
                    )}
                </div>
            </main>

            {/* Item Detail Modal */}
            {selectedItem && (
                <ItemDetailModal item={selectedItem} onClose={() => setSelectedItem(null)} />
            )}
        </div>
    );
};

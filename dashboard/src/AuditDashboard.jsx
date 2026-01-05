const { useState, useEffect, useMemo } = React;

// Status badge component
const StatusBadge = ({ status }) => {
    const statusConfig = {
        'COMPLIANT': { bg: 'bg-green-600', text: 'text-green-100', icon: '\u2713' },
        'MORE_RESTRICTIVE': { bg: 'bg-emerald-600', text: 'text-emerald-100', icon: '\u2713' },
        'NON_COMPLIANT': { bg: 'bg-red-600', text: 'text-red-100', icon: '\u2717' },
        'MISSING_IN_MEL': { bg: 'bg-yellow-600', text: 'text-yellow-100', icon: '\u26a0' },
        'EXTRA_IN_MEL': { bg: 'bg-blue-600', text: 'text-blue-100', icon: '+' },
    };

    const config = statusConfig[status] || { bg: 'bg-gray-600', text: 'text-gray-100', icon: '?' };

    return (
        <span className={`${config.bg} ${config.text} px-2 py-1 rounded text-xs font-medium inline-flex items-center gap-1`}>
            <span>{config.icon}</span>
            {status.replace(/_/g, ' ')}
        </span>
    );
};

// Gauge component for compliance score
const ComplianceGauge = ({ score }) => {
    const rotation = -90 + (score / 100) * 180;

    return (
        <div className="gauge-container">
            <div className="gauge-bg"></div>
            <div className="gauge-inner"></div>
            <div className="gauge-needle" style={{ transform: `rotate(${rotation}deg)` }}></div>
            <div className="absolute bottom-0 left-0 right-0 text-center">
                <span className="text-3xl font-bold text-white">{score.toFixed(1)}%</span>
            </div>
        </div>
    );
};

// Statistics card
const StatCard = ({ title, value, icon, color }) => {
    const colorClasses = {
        green: 'border-green-500 bg-green-500/10',
        red: 'border-red-500 bg-red-500/10',
        yellow: 'border-yellow-500 bg-yellow-500/10',
        blue: 'border-blue-500 bg-blue-500/10',
        gray: 'border-gray-500 bg-gray-500/10',
    };

    return (
        <div className={`rounded-lg border-l-4 ${colorClasses[color]} p-4`}>
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-gray-400 text-sm">{title}</p>
                    <p className="text-2xl font-bold mt-1">{value}</p>
                </div>
                <span className="text-2xl">{icon}</span>
            </div>
        </div>
    );
};

// Non-compliant item card
const NonCompliantCard = ({ item }) => {
    const melInterval = item.details?.mel_interval || 'N/A';
    const mmelInterval = item.details?.mmel_interval || 'N/A';
    const melRequired = item.details?.mel_required || 'N/A';
    const mmelRequired = item.details?.mmel_required || 'N/A';
    const title = item.mel_data?.itemTitle || item.mmel_data?.itemTitle || 'Unknown';

    return (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
            <div className="flex items-start justify-between">
                <div>
                    <h4 className="font-mono text-lg font-bold text-red-400">{item.item_code}</h4>
                    <p className="text-gray-300 mt-1">{title}</p>
                </div>
                <StatusBadge status="NON_COMPLIANT" />
            </div>

            <div className="mt-4 space-y-2">
                {item.issues?.map((issue, idx) => (
                    <div key={idx} className="flex items-start gap-2 text-red-300">
                        <span className="text-red-500">\u2717</span>
                        <span>{issue}</span>
                    </div>
                ))}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div className="bg-navy-800 rounded p-3">
                    <p className="text-gray-500 text-xs mb-1">MEL Values</p>
                    <p>Interval: <span className="font-mono text-white">{melInterval}</span></p>
                    <p>Required: <span className="font-mono text-white">{melRequired}</span></p>
                </div>
                <div className="bg-navy-800 rounded p-3">
                    <p className="text-gray-500 text-xs mb-1">MMEL Values</p>
                    <p>Interval: <span className="font-mono text-white">{mmelInterval}</span></p>
                    <p>Required: <span className="font-mono text-white">{mmelRequired}</span></p>
                </div>
            </div>
        </div>
    );
};

// Detail modal component
const DetailModal = ({ item, onClose }) => {
    if (!item) return null;

    const mel = item.mel_data || {};
    const mmel = item.mmel_data || {};

    const CompareRow = ({ label, melVal, mmelVal }) => {
        const isDifferent = melVal !== mmelVal && melVal && mmelVal;
        return (
            <tr className="border-b border-navy-700">
                <td className="py-2 px-3 text-gray-400">{label}</td>
                <td className={`py-2 px-3 font-mono ${isDifferent ? 'text-yellow-400 bg-yellow-900/20' : ''}`}>
                    {melVal || '-'}
                </td>
                <td className={`py-2 px-3 font-mono ${isDifferent ? 'text-yellow-400 bg-yellow-900/20' : ''}`}>
                    {mmelVal || '-'}
                </td>
            </tr>
        );
    };

    return (
        <div className="fixed inset-0 bg-black/70 modal-backdrop flex items-center justify-center z-50 p-4" onClick={onClose}>
            <div className="bg-navy-800 rounded-xl max-w-4xl w-full max-h-[90vh] overflow-hidden" onClick={e => e.stopPropagation()}>
                {/* Modal header */}
                <div className="bg-navy-700 px-6 py-4 flex items-center justify-between">
                    <div>
                        <h3 className="text-xl font-bold font-mono">{item.item_code}</h3>
                        <p className="text-gray-400">{mel.itemTitle || mmel.itemTitle || 'No title'}</p>
                    </div>
                    <div className="flex items-center gap-4">
                        <StatusBadge status={item.status} />
                        <button onClick={onClose} className="text-gray-400 hover:text-white text-2xl">&times;</button>
                    </div>
                </div>

                {/* Modal body */}
                <div className="p-6 overflow-y-auto max-h-[70vh] scrollbar-thin">
                    {/* Issues */}
                    {item.issues?.length > 0 && (
                        <div className="mb-6 bg-red-900/20 border border-red-800 rounded-lg p-4">
                            <h4 className="text-red-400 font-semibold mb-2">Issues Found</h4>
                            {item.issues.map((issue, idx) => (
                                <p key={idx} className="text-red-300 flex items-center gap-2">
                                    <span>\u2717</span> {issue}
                                </p>
                            ))}
                        </div>
                    )}

                    {/* Comparison table */}
                    <h4 className="text-gray-300 font-semibold mb-3">MEL vs MMEL Comparison</h4>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="bg-navy-700">
                                <th className="py-2 px-3 text-left text-gray-400">Field</th>
                                <th className="py-2 px-3 text-left text-blue-400">MEL</th>
                                <th className="py-2 px-3 text-left text-orange-400">MMEL</th>
                            </tr>
                        </thead>
                        <tbody>
                            <CompareRow label="Item Code" melVal={mel.fullItemCode} mmelVal={mmel.fullItemCode} />
                            <CompareRow label="ATA Chapter" melVal={mel.ataChapter} mmelVal={mmel.ataChapter} />
                            <CompareRow label="ATA Title" melVal={mel.ataTitle} mmelVal={mmel.ataTitle} />
                            <CompareRow
                                label="Rect. Interval"
                                melVal={mel.category || mel.rectificationInterval}
                                mmelVal={mmel.rectificationInterval || mmel.category}
                            />
                            <CompareRow label="Num Installed" melVal={mel.numberInstalled} mmelVal={mmel.numberInstalled} />
                            <CompareRow label="Num Required" melVal={mel.numberRequired} mmelVal={mmel.numberRequired} />
                            <CompareRow
                                label="Maintenance (M)"
                                melVal={mel.requiresMaintenance ? 'Yes' : 'No'}
                                mmelVal={mmel.requiresMaintenance ? 'Yes' : 'No'}
                            />
                            <CompareRow
                                label="Operations (O)"
                                melVal={mel.requiresOperations ? 'Yes' : 'No'}
                                mmelVal={mmel.requiresOperations ? 'Yes' : 'No'}
                            />
                        </tbody>
                    </table>

                    {/* Remarks */}
                    <div className="grid grid-cols-2 gap-4 mt-6">
                        <div>
                            <h4 className="text-blue-400 font-semibold mb-2">MEL Remarks</h4>
                            <div className="bg-navy-900 rounded p-3 text-sm">
                                <p>{mel.remarksText || 'No remarks'}</p>
                                {mel.conditions?.length > 0 && (
                                    <ul className="mt-2 space-y-1 text-gray-400">
                                        {mel.conditions.map((c, i) => <li key={i}>{c}</li>)}
                                    </ul>
                                )}
                            </div>
                        </div>
                        <div>
                            <h4 className="text-orange-400 font-semibold mb-2">MMEL Remarks</h4>
                            <div className="bg-navy-900 rounded p-3 text-sm">
                                <p>{mmel.remarksText || 'No remarks'}</p>
                                {mmel.conditions?.length > 0 && (
                                    <ul className="mt-2 space-y-1 text-gray-400">
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

// Main dashboard component
const AuditDashboard = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedItem, setSelectedItem] = useState(null);

    // Filters
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [ataFilter, setAtaFilter] = useState('ALL');
    const [intervalFilter, setIntervalFilter] = useState('ALL');
    const [searchQuery, setSearchQuery] = useState('');

    // Load data
    useEffect(() => {
        fetch('data/audit_report.json')
            .then(res => {
                if (!res.ok) throw new Error('Failed to load audit data');
                return res.json();
            })
            .then(json => {
                setData(json);
                setLoading(false);
            })
            .catch(err => {
                setError(err.message);
                setLoading(false);
            });
    }, []);

    // Extract unique ATA chapters
    const ataChapters = useMemo(() => {
        if (!data?.results) return [];
        const chapters = new Set();
        data.results.forEach(r => {
            const ata = r.mel_data?.ataChapter || r.mmel_data?.ataChapter;
            if (ata) chapters.add(ata);
        });
        return Array.from(chapters).sort((a, b) => parseInt(a) - parseInt(b));
    }, [data]);

    // Filter results
    const filteredResults = useMemo(() => {
        if (!data?.results) return [];

        return data.results.filter(item => {
            // Status filter
            if (statusFilter !== 'ALL' && item.status !== statusFilter) return false;

            // ATA filter
            const itemAta = item.mel_data?.ataChapter || item.mmel_data?.ataChapter;
            if (ataFilter !== 'ALL' && itemAta !== ataFilter) return false;

            // Interval filter
            const melInterval = item.details?.mel_interval || item.mel_data?.category || item.mel_data?.rectificationInterval;
            const mmelInterval = item.details?.mmel_interval || item.mmel_data?.rectificationInterval;
            if (intervalFilter !== 'ALL') {
                if (melInterval !== intervalFilter && mmelInterval !== intervalFilter) return false;
            }

            // Search filter
            if (searchQuery) {
                const query = searchQuery.toLowerCase();
                const code = item.item_code?.toLowerCase() || '';
                const title = (item.mel_data?.itemTitle || item.mmel_data?.itemTitle || '').toLowerCase();
                if (!code.includes(query) && !title.includes(query)) return false;
            }

            return true;
        });
    }, [data, statusFilter, ataFilter, intervalFilter, searchQuery]);

    // Non-compliant items
    const nonCompliantItems = useMemo(() => {
        if (!data?.results) return [];
        return data.results.filter(r => r.status === 'NON_COMPLIANT');
    }, [data]);

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center">
                    <div className="animate-spin w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full mx-auto"></div>
                    <p className="mt-4 text-gray-400">Loading audit data...</p>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-center bg-red-900/30 border border-red-700 rounded-lg p-8">
                    <p className="text-red-400 text-xl">Error loading data</p>
                    <p className="text-gray-400 mt-2">{error}</p>
                </div>
            </div>
        );
    }

    const summary = data?.summary || {};
    const metadata = data?.metadata || {};

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="bg-navy-800 border-b border-navy-700">
                <div className="max-w-7xl mx-auto px-6 py-6">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold">MEL Conformity Audit</h1>
                            <p className="text-gray-400 mt-1">
                                PC-12 {metadata.mel_aircraft} - {metadata.mel_operator}
                            </p>
                        </div>
                        <div className="flex items-center gap-8">
                            <div className="text-right">
                                <p className="text-gray-500 text-sm">Audit Date</p>
                                <p className="font-mono">{metadata.audit_date?.split('T')[0]}</p>
                            </div>
                            <ComplianceGauge score={summary.compliance_score || 0} />
                        </div>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-6 py-8">
                {/* Statistics Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 mb-8">
                    <StatCard title="MMEL Items" value={summary.total_mmel_items} icon="\ud83d\udcd8" color="gray" />
                    <StatCard title="MEL Items" value={summary.total_mel_items} icon="\ud83d\udcd7" color="gray" />
                    <StatCard title="Compliant" value={summary.compliant} icon="\u2713" color="green" />
                    <StatCard title="More Restrictive" value={summary.more_restrictive} icon="\u2713" color="green" />
                    <StatCard title="Non-Compliant" value={summary.non_compliant} icon="\u2717" color="red" />
                    <StatCard title="Missing in MEL" value={summary.missing_in_mel} icon="\u26a0" color="yellow" />
                    <StatCard title="Extra in MEL" value={summary.extra_in_mel} icon="+" color="blue" />
                </div>

                {/* Non-Compliant Section */}
                {nonCompliantItems.length > 0 && (
                    <section className="mb-8">
                        <h2 className="text-xl font-bold text-red-400 mb-4 flex items-center gap-2">
                            <span>\u26a0</span> Non-Compliant Items ({nonCompliantItems.length})
                        </h2>
                        <div className="grid md:grid-cols-2 gap-4">
                            {nonCompliantItems.map(item => (
                                <NonCompliantCard key={item.item_code} item={item} />
                            ))}
                        </div>
                    </section>
                )}

                {/* Filters */}
                <section className="bg-navy-800 rounded-lg p-4 mb-6">
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                        <div>
                            <label className="block text-gray-400 text-sm mb-1">Search</label>
                            <input
                                type="text"
                                placeholder="Code or title..."
                                value={searchQuery}
                                onChange={e => setSearchQuery(e.target.value)}
                                className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-gray-400 text-sm mb-1">Status</label>
                            <select
                                value={statusFilter}
                                onChange={e => setStatusFilter(e.target.value)}
                                className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="ALL">All Status</option>
                                <option value="COMPLIANT">Compliant</option>
                                <option value="MORE_RESTRICTIVE">More Restrictive</option>
                                <option value="NON_COMPLIANT">Non-Compliant</option>
                                <option value="MISSING_IN_MEL">Missing in MEL</option>
                                <option value="EXTRA_IN_MEL">Extra in MEL</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-gray-400 text-sm mb-1">ATA Chapter</label>
                            <select
                                value={ataFilter}
                                onChange={e => setAtaFilter(e.target.value)}
                                className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="ALL">All Chapters</option>
                                {ataChapters.map(ata => (
                                    <option key={ata} value={ata}>ATA {ata}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="block text-gray-400 text-sm mb-1">Interval</label>
                            <select
                                value={intervalFilter}
                                onChange={e => setIntervalFilter(e.target.value)}
                                className="w-full bg-navy-900 border border-navy-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="ALL">All Intervals</option>
                                <option value="A">A (most restrictive)</option>
                                <option value="B">B</option>
                                <option value="C">C</option>
                                <option value="D">D (least restrictive)</option>
                            </select>
                        </div>
                        <div className="flex items-end">
                            <button
                                onClick={() => {
                                    setStatusFilter('ALL');
                                    setAtaFilter('ALL');
                                    setIntervalFilter('ALL');
                                    setSearchQuery('');
                                }}
                                className="w-full bg-navy-700 hover:bg-navy-600 rounded px-3 py-2 text-sm transition-colors"
                            >
                                Clear Filters
                            </button>
                        </div>
                    </div>
                </section>

                {/* Results Table */}
                <section className="bg-navy-800 rounded-lg overflow-hidden">
                    <div className="px-4 py-3 bg-navy-700 flex items-center justify-between">
                        <h3 className="font-semibold">Audit Results</h3>
                        <span className="text-gray-400 text-sm">{filteredResults.length} items</span>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-navy-900 text-gray-400">
                                    <th className="text-left py-3 px-4">Item Code</th>
                                    <th className="text-left py-3 px-4">Title</th>
                                    <th className="text-left py-3 px-4">ATA</th>
                                    <th className="text-left py-3 px-4">Status</th>
                                    <th className="text-left py-3 px-4">MEL Int.</th>
                                    <th className="text-left py-3 px-4">MMEL Int.</th>
                                    <th className="text-left py-3 px-4">Issue</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredResults.map((item, idx) => {
                                    const title = item.mel_data?.itemTitle || item.mmel_data?.itemTitle || '-';
                                    const ata = item.mel_data?.ataChapter || item.mmel_data?.ataChapter || '-';
                                    const melInt = item.details?.mel_interval || item.mel_data?.category || '-';
                                    const mmelInt = item.details?.mmel_interval || item.mmel_data?.rectificationInterval || '-';
                                    const issue = item.issues?.join('; ') || '-';

                                    return (
                                        <tr
                                            key={item.item_code}
                                            onClick={() => setSelectedItem(item)}
                                            className={`border-b border-navy-700 hover:bg-navy-700/50 cursor-pointer transition-colors ${
                                                item.status === 'NON_COMPLIANT' ? 'bg-red-900/10' : ''
                                            }`}
                                        >
                                            <td className="py-3 px-4 font-mono font-medium">{item.item_code}</td>
                                            <td className="py-3 px-4 max-w-xs truncate">{title}</td>
                                            <td className="py-3 px-4">{ata}</td>
                                            <td className="py-3 px-4"><StatusBadge status={item.status} /></td>
                                            <td className="py-3 px-4 font-mono">{melInt}</td>
                                            <td className="py-3 px-4 font-mono">{mmelInt}</td>
                                            <td className="py-3 px-4 max-w-xs truncate text-gray-400">{issue}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    {filteredResults.length === 0 && (
                        <div className="text-center py-12 text-gray-500">
                            No items match your filters
                        </div>
                    )}
                </section>
            </main>

            {/* Detail Modal */}
            {selectedItem && (
                <DetailModal item={selectedItem} onClose={() => setSelectedItem(null)} />
            )}
        </div>
    );
};

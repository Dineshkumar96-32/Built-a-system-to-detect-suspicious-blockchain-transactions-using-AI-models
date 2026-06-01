import { useState, useEffect } from 'react'
import { api } from '../services/api'

export default function Settings() {
  const [webhookUrl, setWebhookUrl] = useState('')
  const [webhookEnabled, setWebhookEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')

  useEffect(() => {
    // We need to fetch the current settings
    const fetchSettings = async () => {
      try {
        const data = await api.getSettings()
        setWebhookUrl(data.webhook_url || '')
        setWebhookEnabled(data.webhook_enabled || false)
      } catch (err) {
        console.error('Failed to fetch settings', err)
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setStatusMsg('')
    try {
      await api.updateSettings({
        webhook_enabled: webhookEnabled,
        webhook_url: webhookUrl,
      })
      setStatusMsg('Settings saved successfully!')
    } catch (err) {
      console.error(err)
      setStatusMsg('Error saving settings.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 text-gray-400">Loading settings...</div>
  }

  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold mb-6 text-white tracking-tight">System Settings</h1>
      
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 shadow-xl relative overflow-hidden">
        {/* Glow effect */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-orange-500/10 blur-3xl rounded-full" />
        
        <h2 className="text-lg font-bold mb-4 text-orange-400 flex items-center gap-2">
          <span>🚨</span> External Alerting (Webhooks)
        </h2>
        <p className="text-gray-400 text-sm mb-6">
          Configure BlockShield to push high-severity transaction alerts directly to your Slack or Discord workspace.
        </p>

        <div className="space-y-6 relative z-10">
          <div className="flex items-center gap-3">
            <label className="relative inline-flex items-center cursor-pointer">
              <input 
                type="checkbox" 
                className="sr-only peer"
                checked={webhookEnabled}
                onChange={(e) => setWebhookEnabled(e.target.checked)}
              />
              <div className="w-11 h-6 bg-gray-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600"></div>
            </label>
            <span className="text-sm font-bold text-gray-300">Enable Webhook Dispatch</span>
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
              Webhook URL
            </label>
            <input
              type="text"
              className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 text-sm text-gray-100 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition-colors"
              placeholder="https://hooks.slack.com/services/... or https://discord.com/api/webhooks/..."
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              disabled={!webhookEnabled}
            />
          </div>

          <div className="flex items-center gap-4 pt-4 border-t border-gray-800/50">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2.5 bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-500 hover:to-red-500 text-white font-bold text-sm rounded-lg shadow-lg shadow-orange-900/20 disabled:opacity-50 transition-all"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
            
            {statusMsg && (
              <span className={`text-sm font-bold ${statusMsg.includes('Error') ? 'text-red-400' : 'text-green-400'}`}>
                {statusMsg}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

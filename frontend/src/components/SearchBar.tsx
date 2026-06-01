// src/components/SearchBar.tsx
import { useState } from 'react'

interface Props {
  onSearch: (query: string) => void
  isSearching?: boolean
}

export function SearchBar({ onSearch, isSearching }: Props) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim().length >= 2) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="relative group w-full max-w-md">
      <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-gray-500 group-focus-within:text-orange-500 transition-colors">
        {isSearching ? (
          <div className="w-4 h-4 border-2 border-orange-500 border-t-transparent rounded-full animate-spin" />
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        )}
      </div>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search hash or address..."
        className="w-full bg-gray-900/50 border border-gray-800 rounded-lg py-2 pl-10 pr-4 text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500/50 focus:border-orange-500/50 transition-all"
      />
      <div className="absolute inset-y-0 right-3 flex items-center">
        <kbd className="hidden sm:inline-flex items-center px-1.5 py-0.5 border border-gray-700 rounded text-[10px] font-mono text-gray-500 bg-gray-800">
          ENTER
        </kbd>
      </div>
    </form>
  )
}

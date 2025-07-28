import { Send } from 'lucide-react'
import { Button } from './ui/Button'

export const MessageInput = ({ 
  value, 
  onChange, 
  onSubmit, 
  disabled, 
  placeholder = "Type your message..." 
}) => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit(e)
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex gap-3 p-4 border-t border-gray-200 bg-white">
      <div className="flex-1 relative group">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="relative w-full resize-none border border-gray-300 rounded-lg px-4 py-3 text-sm text-gray-900 placeholder:text-gray-400 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 overflow-hidden"
          style={{
            minHeight: '44px',
            maxHeight: '120px',
            overflowY: value.split('\n').length > 3 || value.length > 200 ? 'auto' : 'hidden'
          }}
          onInput={(e) => {
            e.target.style.height = '44px'
            const scrollHeight = e.target.scrollHeight
            e.target.style.height = Math.min(scrollHeight, 120) + 'px'
          }}
        />
      </div>
      <Button 
        type="submit" 
        size="icon"
        disabled={disabled || !value.trim()}
        className="shrink-0 relative overflow-hidden group"
      >
        <Send className="h-4 w-4 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 duration-200" />
      </Button>
    </form>
  )
}
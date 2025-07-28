import { Plus, MessageSquare, Shield } from 'lucide-react'
import { Button } from './ui/Button'
import { truncateGUID } from '../lib/utils'

export const ConversationList = ({ 
  conversations, 
  currentConversationId, 
  onSelectConversation, 
  onNewConversation 
}) => {
  return (
    <div className="w-72 bg-gray-100 border-r border-gray-200 flex flex-col h-full">
      <div className="p-4 border-b border-gray-200 bg-white">
        <Button 
          onClick={onNewConversation} 
          className="w-full justify-start gap-3 text-white shadow-sm hover:shadow-md transition-all duration-200 group"
          variant="default"
        >
          <Plus className="h-4 w-4 transition-transform group-hover:rotate-90 duration-300" />
          <span className="font-medium">New Session</span>
        </Button>
      </div>
      
      <div className="flex-1 overflow-y-auto custom-scrollbar bg-gray-100">
        <div className="p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-12 animate-in fade-in duration-500">
              <MessageSquare className="h-10 w-10 mx-auto mb-3 text-gray-400" />
              <p className="text-sm text-gray-600">No active sessions</p>
              <p className="text-xs text-gray-500 mt-2">Create a new secure session above</p>
            </div>
          ) : (
            conversations.map((conversation, index) => (
              <button
                key={conversation.id}
                onClick={() => onSelectConversation(conversation.id)}
                className={`w-full text-left px-3 py-2.5 rounded-md text-sm transition-all duration-200 hover:translate-x-0.5 animate-in slide-in-from-left ${
                  currentConversationId === conversation.id
                    ? 'bg-white text-gray-900 shadow-sm border border-gray-200'
                    : 'text-gray-700 hover:bg-white hover:text-gray-900 hover:shadow-sm'
                }`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-center gap-2.5">
                  <MessageSquare className={`h-4 w-4 ${
                    currentConversationId === conversation.id ? 'text-blue-600' : 'text-gray-400'
                  }`} />
                  <span className="truncate font-medium">
                    Session {truncateGUID(conversation.id.toString())}
                  </span>
                </div>
                {conversation.created_at && (
                  <div className="text-xs text-gray-500 mt-1 ml-6.5">
                    {new Date(conversation.created_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })}
                  </div>
                )}
              </button>
            ))
          )}
        </div>
      </div>
      
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex items-center justify-center gap-2 text-xs text-gray-500">
          <Shield className="h-3 w-3" />
          <span>GovCloud AI v2.0</span>
        </div>
      </div>
    </div>
  )
}
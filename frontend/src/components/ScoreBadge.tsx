interface ScoreBadgeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
  band?: string;
  confidence?: number;
}

function getBandLabel(s: number): string {
  if (s >= 80) return '高度匹配';
  if (s >= 61) return '基本满足';
  if (s >= 41) return '部分满足';
  if (s >= 21) return '大部分不满足';
  return '完全不匹配';
}

function getConfidenceColor(c: number): string {
  if (c >= 0.8) return 'bg-green-500';
  if (c >= 0.6) return 'bg-yellow-500';
  return 'bg-red-500';
}

export default function ScoreBadge({ score, size = 'md', band, confidence }: ScoreBadgeProps) {
  const getColor = (s: number) => {
    if (s >= 80) return 'bg-green-500';
    if (s >= 60) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const sizeClasses = {
    sm: 'w-10 h-10 text-sm',
    md: 'w-14 h-14 text-lg',
    lg: 'w-20 h-20 text-2xl',
  };

  const bandLabel = band || getBandLabel(score);

  return (
    <div className="flex flex-col items-center">
      <div
        className={`${sizeClasses[size]} ${getColor(score)} rounded-full flex items-center justify-center text-white font-bold shadow-sm`}
        title={`${bandLabel}${confidence !== undefined ? ` · 置信度 ${Math.round(confidence * 100)}%` : ''}`}
      >
        {Math.round(score)}
      </div>
      {size === 'lg' && (
        <span className="text-xs text-gray-500 mt-1.5">{bandLabel}</span>
      )}
      {confidence !== undefined && (
        <div className="flex items-center mt-1 space-x-1">
          <div className={`w-2 h-2 rounded-full ${getConfidenceColor(confidence)}`} />
          <span className="text-xs text-gray-400">
            {Math.round(confidence * 100)}% 置信
          </span>
        </div>
      )}
    </div>
  );
}

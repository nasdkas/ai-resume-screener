interface ScoreBadgeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg';
}

export default function ScoreBadge({ score, size = 'md' }: ScoreBadgeProps) {
  const getColor = (s: number) => {
    if (s >= 80) return 'bg-green-500';
    if (s >= 51) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  const sizeClasses = {
    sm: 'w-10 h-10 text-sm',
    md: 'w-14 h-14 text-lg',
    lg: 'w-20 h-20 text-2xl',
  };

  return (
    <div
      className={`${sizeClasses[size]} ${getColor(score)} rounded-full flex items-center justify-center text-white font-bold`}
    >
      {Math.round(score)}
    </div>
  );
}

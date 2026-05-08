interface SkillTagProps {
  skill: string;
  matched?: boolean;
}

export default function SkillTag({ skill, matched = false }: SkillTagProps) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        matched
          ? 'bg-green-100 text-green-800'
          : 'bg-blue-100 text-blue-800'
      }`}
    >
      {skill}
    </span>
  );
}

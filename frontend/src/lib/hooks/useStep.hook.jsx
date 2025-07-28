import { useState } from "react";

const useStep = (steps) => {
    const [step, setStep] = useState(1);

    const next = () => setStep(c => c !== steps ? c + 1 : c);
    const prev = () => setStep(c => c > 1 ? c - 1 : c);

    return { step, next, prev };
};

export default useStep
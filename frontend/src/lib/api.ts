// API service pointing to local backend, with fallback mock data

export type DetectionResult = {
  score: number;
  verdict: 'AUTHENTIC' | 'SUSPICIOUS' | 'CLONED';
  details: {
    spectralJitter: number;
    harmonicArtifacts: number;
    phonemeConsistency: number;
    neuralSynthesisMarkers: number;
  };
  duration: number;
  language: string;
};

const MOCK_DELAY = 1500;

const USE_MOCK = false; // Turned off to use real backend

export async function analyzeAudio(audioFile: File | Blob, language: string): Promise<DetectionResult> {
  if (USE_MOCK) {
    return new Promise((resolve) => {
      setTimeout(() => {
        // Randomize score for realism
        const isSuspicious = Math.random() > 0.5;
        const score = isSuspicious ? 75 + Math.random() * 20 : 5 + Math.random() * 15;
        
        resolve({
          score,
          verdict: score > 70 ? 'CLONED' : score > 40 ? 'SUSPICIOUS' : 'AUTHENTIC',
          details: {
            spectralJitter: Math.random() * 100,
            harmonicArtifacts: Math.random() * 100,
            phonemeConsistency: 100 - Math.random() * 40,
            neuralSynthesisMarkers: score, // Highly correlated with final score
          },
          duration: 3.2,
          language: language,
        });
      }, MOCK_DELAY);
    });
  }

  // Real backend implementation
  const formData = new FormData();
  // FastAPI expects 'file' parameter
  formData.append('file', audioFile);

  try {
    const response = await fetch('http://localhost:8000/analyze', {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    
    // Map FastAPI backend response to our DetectionResult type
    let mappedVerdict: 'AUTHENTIC' | 'SUSPICIOUS' | 'CLONED' = 'AUTHENTIC';
    if (data.verdict.includes("AI-Generated") || data.verdict === "SYNTHETIC CLONE DETECTED") {
      mappedVerdict = 'CLONED';
    } else if (data.verdict.includes("UNCERTAIN") || data.risk_band === "ELEVATED") {
      mappedVerdict = 'SUSPICIOUS';
    }

    return {
      score: data.prob_ai * 100,
      verdict: mappedVerdict,
      details: {
        spectralJitter: data.confidence * 100, // mapped to UI stats for visual representation
        harmonicArtifacts: data.prob_ai * 80, 
        phonemeConsistency: 100 - (data.prob_ai * 60),
        neuralSynthesisMarkers: data.prob_ai * 100, 
      },
      duration: data.duration_s || 0,
      language: language,
    };
  } catch (error) {
    console.error("Failed to call backend, please ensure FastAPI is running on port 8000", error);
    throw error;
  }
}

"""
DKT+ (Deep Knowledge Tracing with Regularization) model.

Status: ARCHITECTURE IMPLEMENTED
Training: BLOCKED - same data requirements as AKT.

Requires PyTorch.
"""
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    
if PYTORCH_AVAILABLE:
    class DKTPlusModel(nn.Module):
        def __init__(self, n_skills: int, hidden_size: int = 128, dropout: float = 0.2):
            super().__init__()
            self.lstm = nn.LSTM(n_skills * 2, hidden_size, batch_first=True)
            self.dropout = nn.Dropout(dropout)
            self.fc = nn.Linear(hidden_size, n_skills)
            self.sigmoid = nn.Sigmoid()
        
        def forward(self, x):
            # x: (batch, seq_len, n_skills*2) one-hot encoded interactions
            out, _ = self.lstm(x)
            out = self.dropout(out)
            return self.sigmoid(self.fc(out))

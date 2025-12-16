# Stale State Detection Improvements

## Issue Analysis
The terminal was still experiencing stale state issues where it would get stuck in "refreshing terminal... 3/3" state without recovering properly, requiring manual browser refresh.

## Root Cause
1. **Slow Detection**: 20-second delay before attempting refresh was too long
2. **Ineffective Refresh**: Simple refresh commands weren't aggressive enough
3. **Long Recovery Time**: 60-second wait before forced reconnection was excessive
4. **Weak Refresh Strategies**: Gentle refresh commands often failed to wake up stale terminals

## Solution Implementation

### 1. Faster Stale State Detection
```javascript
// Before: 20 seconds before refresh attempts
if (timeSinceLastOutput > 20000 && isConnected && terminalRefreshAttempts < 3)

// After: 15 seconds before refresh attempts  
if (timeSinceLastOutput > 15000 && isConnected && terminalRefreshAttempts < 3)
```

### 2. More Aggressive Refresh Strategies
```javascript
// Before: Gentle refresh commands
if (terminalRefreshAttempts === 2) {
    ws.send(JSON.stringify({ input: '\n' }));
}

// After: More effective refresh commands
if (terminalRefreshAttempts === 2) {
    ws.send(JSON.stringify({ input: '\r' })); // Carriage return instead of newline
} else if (terminalRefreshAttempts === 3) {
    // Triple-command aggressive refresh
    ws.send(JSON.stringify({ input: '\x03' })); // Ctrl+C (interrupt)
    setTimeout(() => ws.send(JSON.stringify({ input: '\x0C' })), 100); // Ctrl+L (clear)
    setTimeout(() => ws.send(JSON.stringify({ input: '\r' })), 200);   // Enter
}
```

### 3. Faster Recovery Timeout
```javascript
// Before: 60 seconds before forced reconnection
if (timeSinceLastOutput > 60000 && terminalRefreshAttempts >= 3)

// After: 35 seconds before forced reconnection
if (timeSinceLastOutput > 35000 && terminalRefreshAttempts >= 3)
```

### 4. Improved Response Detection
```javascript
// Before: 2-second delay, 3-second response window
setTimeout(() => {
    const recentOutput = Date.now() - lastOutputTime;
    if (recentOutput < 3000) {
        terminalRefreshAttempts = 0;
    }
}, 2000);

// After: 1.5-second delay, 2-second response window
setTimeout(() => {
    const recentOutput = Date.now() - lastOutputTime;
    if (recentOutput < 2000) {
        terminalRefreshAttempts = 0;
        updateStatus('Connected', 'success');
    } else if (terminalRefreshAttempts >= 3) {
        console.log('All refresh attempts failed, will force reconnection soon...');
    }
}, 1500);
```

## Timeline Improvements

### Before (Slow Recovery)
```
0s:   Terminal becomes stale
20s:  First refresh attempt (gentle)
25s:  Second refresh attempt (newline)
30s:  Third refresh attempt (clear screen)
60s:  Force reconnection
```
**Total recovery time: 60+ seconds**

### After (Fast Recovery)
```
0s:   Terminal becomes stale
15s:  First refresh attempt (gentle)
18s:  Second refresh attempt (carriage return)
21s:  Third refresh attempt (aggressive: Ctrl+C + Ctrl+L + Enter)
35s:  Force reconnection if still unresponsive
```
**Total recovery time: 35 seconds maximum**

## Key Benefits

1. **Faster Detection**: 25% faster initial detection (15s vs 20s)
2. **More Effective Recovery**: Aggressive multi-command refresh strategy
3. **Quicker Fallback**: 42% faster forced reconnection (35s vs 60s)
4. **Better User Feedback**: Clearer status messages and faster status updates
5. **Reduced Frustration**: Much shorter wait times for terminal recovery

## Expected Results
- ✅ Faster detection of stale terminal states
- ✅ More effective refresh commands that actually wake up stale terminals
- ✅ Quicker fallback to forced reconnection when refresh fails
- ✅ Better user experience with shorter recovery times
- ✅ Reduced need for manual browser refresh

This should significantly improve the terminal's ability to recover from stale states automatically, reducing user frustration and the need for manual intervention.
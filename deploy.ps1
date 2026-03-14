# PowerShell script for direct Vercel deployment
# Run this script to deploy directly to Vercel

Write-Host "🚀 Starting Vercel Deployment..." -ForegroundColor Green

# Check if Vercel CLI is installed
$vercelInstalled = Get-Command vercel -ErrorAction SilentlyContinue

if (-not $vercelInstalled) {
    Write-Host "📦 Installing Vercel CLI..." -ForegroundColor Yellow
    npm install -g vercel
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to install Vercel CLI" -ForegroundColor Red
        exit 1
    }
}

# Check if user is logged in
Write-Host "🔐 Checking Vercel login status..." -ForegroundColor Yellow
$loginCheck = vercel whoami 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Not logged in. Please login first:" -ForegroundColor Yellow
    Write-Host "   vercel login" -ForegroundColor Cyan
    vercel login
}

# Read .env file for API_ID and API_HASH
$envFile = ".env"
if (Test-Path $envFile) {
    Write-Host "📝 Reading .env file..." -ForegroundColor Yellow
    $envContent = Get-Content $envFile
    $apiId = ($envContent | Select-String "API_ID=(.+)").Matches.Groups[1].Value
    $apiHash = ($envContent | Select-String "API_HASH=(.+)").Matches.Groups[1].Value
    
    if ($apiId -and $apiHash) {
        Write-Host "✅ Found API_ID and API_HASH in .env" -ForegroundColor Green
    } else {
        Write-Host "⚠️  API_ID or API_HASH not found in .env" -ForegroundColor Yellow
        Write-Host "   Make sure to add them in Vercel dashboard after deployment" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  .env file not found" -ForegroundColor Yellow
    Write-Host "   Make sure to add environment variables in Vercel dashboard" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📋 Important: After deployment, add these environment variables in Vercel dashboard:" -ForegroundColor Cyan
Write-Host "   - API_ID" -ForegroundColor White
Write-Host "   - API_HASH" -ForegroundColor White
Write-Host "   - API_KEY=BSMQ9T" -ForegroundColor White
Write-Host "   - SESSION_STRING=1BVtsOJABuyqDGOMuc_PnUB_xa5-Bvmn9UBkXblN_O0aw-mdjx9WdtBZsBegrZyNyAcTQ2VYe4AzWbfo3AiishskcNSb8jLINZRnZoL5VlanB1L7pQit1QktNIEs2qtqspLt9FKVEeS5kR8AA55NYmyy7z0-WLsWGepah6XBJolLh62BiuRoiutq7Gr2Zb-82MhAL3ldbzI_V4d1eefMnNgJZCxAJ-sh1uFWYUBFpxVER3Jduk-DC-hG06w_VF09U98agD4wUSmA0EIldaTg-qsxCXdpIx_i-ZMpUF1KD6ShFBndUZblpHIvARyx-k4MVTf4XyyzCcoc-HAk6lh3KHNh69NPYs9g=" -ForegroundColor White
Write-Host ""

# Deploy to Vercel
Write-Host "🚀 Deploying to Vercel..." -ForegroundColor Green
vercel --prod

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Deployment successful!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📝 Next steps:" -ForegroundColor Cyan
    Write-Host "   1. Go to Vercel dashboard" -ForegroundColor White
    Write-Host "   2. Open your project → Settings → Environment Variables" -ForegroundColor White
    Write-Host "   3. Add all required environment variables" -ForegroundColor White
    Write-Host "   4. Redeploy: vercel --prod" -ForegroundColor White
    Write-Host ""
    Write-Host "🔗 Setup keep-alive:" -ForegroundColor Cyan
    Write-Host "   Visit: https://cron-job.org" -ForegroundColor White
    Write-Host "   URL: https://your-project.vercel.app/api/keepalive" -ForegroundColor White
    Write-Host "   Schedule: Every 5 minutes" -ForegroundColor White
} else {
    Write-Host "❌ Deployment failed" -ForegroundColor Red
    exit 1
}


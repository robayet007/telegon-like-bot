#!/bin/bash
# Direct Vercel Deployment Script

echo "🚀 Deploying to Vercel..."

# Install Vercel CLI if not installed
if ! command -v vercel &> /dev/null; then
    echo "📦 Installing Vercel CLI..."
    npm install -g vercel
fi

# Set environment variables
export API_ID="your_api_id_here"
export API_HASH="your_api_hash_here"
export API_KEY="BSMQ9T"
export SESSION_STRING="1BVtsOJABuyqDGOMuc_PnUB_xa5-Bvmn9UBkXblN_O0aw-mdjx9WdtBZsBegrZyNyAcTQ2VYe4AzWbfo3AiishskcNSb8jLINZRnZoL5VlanB1L7pQit1QktNIEs2qtqspLt9FKVEeS5kR8AA55NYmyy7z0-WLsWGepah6XBJolLh62BiuRoiutq7Gr2Zb-82MhAL3ldbzI_V4d1eefMnNgJZCxAJ-sh1uFWYUBFpxVER3Jduk-DC-hG06w_VF09U98agD4wUSmA0EIldaTg-qsxCXdpIx_i-ZMpUF1KD6ShFBndUZblpHIvARyx-k4MVTf4XyyzCcoc-HAk6lh3KHNh69NPYs9g="

# Deploy to Vercel
vercel --prod

echo "✅ Deployment complete!"


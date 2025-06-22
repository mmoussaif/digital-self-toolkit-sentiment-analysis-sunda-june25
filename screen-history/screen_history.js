#!/usr/bin/env node

/**
 * Screen History Data Extractor
 *
 * Extracts recent screen capture data using the screenpipe SDK
 * and saves it to a JSON file in ./data/
 */

// @ts-nocheck
import { pipe } from "@screenpipe/js";
import { mkdirSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Get recent screen activity data using the demo code approach
 * @param {number} hoursBack - Number of hours back to look for data
 * @returns {Promise<Object>} Combined activity data
 */
async function getRecentActivity(hoursBack = 1) {
  // Get the last hour of screen activity (following the demo)
  const startTime = new Date(
    Date.now() - hoursBack * 60 * 60 * 1000
  ).toISOString();
  const endTime = new Date().toISOString();

  console.log(`Fetching activity from the last ${hoursBack} hour(s)...`);
  console.log(`Time range: ${startTime} to ${endTime}`);

  try {
    // Get recent OCR data using the demo approach
    console.log("Fetching recent OCR data...");
    const results = await pipe.queryScreenpipe({
      contentType: "ocr",
      startTime,
      endTime,
      limit: 50,
      includeFrames: true, // include base64 encoded images
    });

    console.log(`Found ${results.data.length} OCR results`);

    // Process results as shown in demo
    const processedResults = [];
    for (const item of results.data) {
      console.log(`At ${item.content.timestamp}:`);
      console.log(`Text: ${item.content.text}`);

      const processedItem = {
        timestamp: item.content.timestamp,
        text: item.content.text,
        app_name: item.content.app_name || null,
        window_name: item.content.window_name || null,
        hasFrame: !!item.content.frame,
      };

      if (item.content.frame) {
        console.log("  📸 Has screenshot data");
        // Store frame data (base64) for potential use
        processedItem.frame = item.content.frame;
      }

      processedResults.push(processedItem);
    }

    // Also try to get some audio data
    console.log("Fetching recent audio data...");
    const audioResults = await pipe.queryScreenpipe({
      contentType: "audio",
      startTime,
      endTime,
      limit: 20,
    });

    console.log(`Found ${audioResults.data.length} audio results`);

    // Create app usage summary from OCR data
    const appUsage = {};
    results.data.forEach((item) => {
      if (item.content.app_name) {
        const appName = item.content.app_name;
        if (!appUsage[appName]) {
          appUsage[appName] = {
            name: appName,
            events: 0,
            windows: new Set(),
            firstSeen: item.content.timestamp,
            lastSeen: item.content.timestamp,
          };
        }
        appUsage[appName].events++;
        if (item.content.window_name) {
          appUsage[appName].windows.add(item.content.window_name);
        }
      }
    });

    // Convert to array and sort
    const appUsageSummary = Object.values(appUsage)
      .map((app) => ({
        ...app,
        windows: Array.from(app.windows),
        windowCount: app.windows.size,
      }))
      .sort((a, b) => b.events - a.events);

    // Compile the data
    const activityData = {
      metadata: {
        extractedAt: new Date().toISOString(),
        hoursBack,
        timeRange: {
          startTime,
          endTime,
        },
        totalResults: {
          ocr: results.data.length,
          audio: audioResults.data.length,
        },
      },
      ocrActivity: processedResults,
      audioTranscriptions: audioResults.data,
      appUsageSummary,
      rawOcrData: results.data, // Keep original data structure
    };

    console.log(`✓ Processed ${processedResults.length} OCR events`);
    console.log(`✓ Found ${audioResults.data.length} audio transcriptions`);
    console.log(
      `✓ Found activity from ${appUsageSummary.length} different apps`
    );

    return activityData;
  } catch (error) {
    console.error("Error fetching activity data:", error);
    throw error;
  }
}

/**
 * Save data to JSON file
 * @param {Object} data - Data to save
 * @param {string} filename - Optional filename
 * @returns {string} Path to saved file
 */
function saveToJson(data, filename = undefined) {
  // Create data directory if it doesn't exist
  const dataDir = join(__dirname, "data");
  mkdirSync(dataDir, { recursive: true });

  if (!filename) {
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    filename = `screenpipe_activity_${timestamp}.json`;
  }

  const outputPath = join(dataDir, filename);

  try {
    writeFileSync(outputPath, JSON.stringify(data, null, 2), "utf8");
    console.log(`✓ Data saved to: ${outputPath}`);
    return outputPath;
  } catch (error) {
    console.error("Error saving file:", error);
    throw error;
  }
}

/**
 * Main function
 */
async function main() {
  try {
    console.log("🔍 Starting screenpipe activity extraction...\n");

    // Extract recent activity (last 1 hour by default)
    const activityData = await getRecentActivity(1);

    // Save to JSON file
    const outputPath = saveToJson(activityData);

    console.log(
      "\n✅ Success! Recent screenpipe activity has been extracted and saved."
    );
    console.log(`📁 File location: ${outputPath}`);

    // Print summary
    console.log("\n📊 Summary:");
    console.log(`   OCR events: ${activityData.ocrActivity.length}`);
    console.log(
      `   Audio transcriptions: ${activityData.audioTranscriptions.length}`
    );
    console.log(
      `   Screenshots with frames: ${
        activityData.ocrActivity.filter((item) => item.hasFrame).length
      }`
    );
    console.log(
      `   Apps with activity: ${activityData.appUsageSummary.length}`
    );

    if (activityData.appUsageSummary.length > 0) {
      console.log("\n🏆 Top 5 most active apps:");
      activityData.appUsageSummary.slice(0, 5).forEach((app, index) => {
        console.log(
          `   ${index + 1}. ${app.name}: ${app.events} events (${
            app.windowCount
          } windows)`
        );
      });
    }
  } catch (error) {
    console.error("❌ Error:", error.message);

    if (
      error.message.includes("ECONNREFUSED") ||
      error.message.includes("fetch")
    ) {
      console.log("\n💡 Make sure screenpipe is running:");
      console.log(
        "   1. Install screenpipe: curl -fsSL get.screenpi.pe/cli | sh"
      );
      console.log("   2. Start screenpipe: screenpipe");
      console.log("   3. Run this script again");
    }

    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

/**
 * RetroTV — schedule.js
 *
 * The core content database and scheduling engine.
 * index.html inlines this script directly — keep both in sync.
 *
 * ─────────────────────────────────────────────────────────────────────────
 * ADDING CONTENT
 *
 * YouTube (when embedding is allowed by the owner):
 *   { type: 'youtube', videoId: 'the-11-char-ID', durationMins: N, ... }
 *   NOTE: Many official channels block embedding (error 153). If that
 *   happens the TV will show "Signal Lost" and auto-skip after 3 seconds.
 *   Always test a video at: https://www.youtube.com/embed/VIDEO_ID
 *
 * Internet Archive (public domain / freely licensed — always embeds):
 *   { type: 'archive', videoId: 'the-identifier-from-archive.org/details/ID', ... }
 *   Find the identifier in the URL when browsing archive.org/details/IDENTIFIER
 *
 * EPISODE DURATION:
 *   Set durationMins accurately — this drives the "on-air" position calculation.
 *   For archive.org collections (multiple videos), estimate the total runtime.
 * ─────────────────────────────────────────────────────────────────────────
 */
const CHANNELS = [
  // ─────────────────────────────────────────────
  // CH 3 — Popeye the Sailor
  // Source: archive.org — public domain Famous Studios shorts (1950s)
  // ─────────────────────────────────────────────
  {
    number: 3,
    name: "Popeye the Sailor",
    era: "Golden Age",
    color: "#2980b9",
    description: "Spinach-powered adventures — Popeye vs Bluto, every episode",
    playlist: [
      {
        title: "Taxi-Turvy",
        show: "Popeye the Sailor",
        year: 1954,
        durationMins: 6,
        type: "archive",
        videoId: "popeye_taxi-turvey",
      },
      {
        title: "Popalong Popeye",
        show: "Popeye the Sailor",
        year: 1952,
        durationMins: 6,
        type: "archive",
        videoId: "popalong-popeye-1952",
      },
      {
        title: "Mister and Mistletoe",
        show: "Popeye the Sailor",
        year: 1955,
        durationMins: 6,
        type: "archive",
        videoId: "popeye-the-sailor-mister-and-mistletoe-1955",
      },
    ]
  },

  // ─────────────────────────────────────────────
  // CH 7 — Betty Boop
  // Source: archive.org — Fleischer Studios, CC licensed
  // BettyBoopCartoons is a collection of 5 shorts (~7 min each = ~35 min)
  // The archive.org player auto-advances through the whole collection
  // ─────────────────────────────────────────────
  {
    number: 7,
    name: "Betty Boop",
    era: "1930s",
    color: "#e91e8c",
    description: "The original animated it-girl — jazz age surrealism at its finest",
    playlist: [
      {
        title: "Betty Boop Shorts",
        show: "Betty Boop",
        year: 1932,
        durationMins: 35,
        type: "archive",
        videoId: "BettyBoopCartoons",
      },
    ]
  },

  // ─────────────────────────────────────────────
  // CH 11 — Looney Tunes
  // Source: archive.org — public domain pre-1978 Warner Bros. shorts
  // ltmm-publicdomain is a large collection; treat as a long block
  // ─────────────────────────────────────────────
  {
    number: 11,
    name: "Looney Tunes",
    era: "Golden Age",
    color: "#8e44ad",
    description: "Bugs, Daffy, Elmer — the golden age of cartoon slapstick",
    playlist: [
      {
        title: "Public Domain Looney Tunes",
        show: "Looney Tunes / Merrie Melodies",
        year: 1930,
        durationMins: 60,
        type: "archive",
        videoId: "ltmm-publicdomain",
      },
    ]
  },

  // ─────────────────────────────────────────────
  // CH 17 — Classic Cartoons Mix
  // Source: archive.org — Disney, Fleischer Color Classics, Popeye
  // ─────────────────────────────────────────────
  {
    number: 17,
    name: "Classic cartoons",
    era: "timeless",
    color: "#16a085",
    description: "Golden age animation — Disney, Fleischer and the pioneers",
    playlist: [
      {
        title: "Steamboat Willie",
        show: "Walt Disney Studios",
        year: 1928,
        durationMins: 8,
        type: "archive",
        videoId: "disneycartoons-publicdomain",
      },
      {
        title: "Somewhere in Dreamland",
        show: "Fleischer Color Classic",
        year: 1936,
        durationMins: 10,
        type: "archive",
        videoId: "pdcartooncollection",
      },
      {
        title: "Taxi-Turvy",
        show: "Popeye the Sailor",
        year: 1954,
        durationMins: 6,
        type: "archive",
        videoId: "popeye_taxi-turvey",
      },
    ]
  },
];

// ─────────────────────────────────────────────
// SCHEDULER ENGINE
// ─────────────────────────────────────────────

/**
 * Given a channel and the current time, work out:
 * - Which episode is "on air" right now
 * - How many seconds into it we are (startOffset)
 *
 * This creates the broadcast illusion: all viewers tuning to the same
 * channel at the same time see the same moment in the same episode.
 */
function getCurrentBroadcast(channel) {
  const now = Math.floor(Date.now() / 1000);
  const totalSeconds = channel.playlist.reduce((sum, ep) => sum + (ep.durationMins * 60), 0);
  if (totalSeconds === 0) return null;
  const positionInCycle = now % totalSeconds;
  let elapsed = 0;
  for (let i = 0; i < channel.playlist.length; i++) {
    const ep = channel.playlist[i];
    const epDuration = ep.durationMins * 60;
    if (positionInCycle < elapsed + epDuration) {
      return {
        episode: ep,
        episodeIndex: i,
        startOffset: Math.floor(positionInCycle - elapsed),
        remainingSeconds: Math.floor((elapsed + epDuration) - positionInCycle),
        channel: channel,
      };
    }
    elapsed += epDuration;
  }
  return {
    episode: channel.playlist[0], episodeIndex: 0,
    startOffset: 0, remainingSeconds: channel.playlist[0].durationMins * 60, channel,
  };
}

/**
 * Get the upcoming schedule for a channel over the next N hours.
 * Used by the TV Guide.
 */
function getScheduleForChannel(channel, hoursAhead = 4) {
  const now = Math.floor(Date.now() / 1000);
  const endTime = now + (hoursAhead * 3600);
  const totalSeconds = channel.playlist.reduce((sum, ep) => sum + (ep.durationMins * 60), 0);
  const schedule = [];
  let cursor = now - (now % totalSeconds);
  while (cursor < endTime) {
    let offset = 0;
    for (const ep of channel.playlist) {
      const epStart = cursor + offset;
      const epEnd = epStart + (ep.durationMins * 60);
      if (epEnd > now && epStart < endTime) {
        schedule.push({ episode: ep, startTime: epStart, endTime: epEnd, isCurrentlyAiring: epStart <= now && epEnd > now });
      }
      offset += ep.durationMins * 60;
    }
    cursor += totalSeconds;
  }
  return schedule;
}

/**
 * Build the embed URL for an episode.
 * enablejsapi=1 on YouTube allows error detection via postMessage.
 */
function getEmbedUrl(episode, startOffset = 0) {
  if (episode.type === 'youtube')
    return `https://www.youtube.com/embed/${episode.videoId}?autoplay=1&start=${startOffset}&rel=0&modestbranding=1&enablejsapi=1`;
  if (episode.type === 'youtube-playlist')
    return `https://www.youtube.com/embed/videoseries?list=${episode.videoId}&autoplay=1&rel=0&modestbranding=1&enablejsapi=1`;
  if (episode.type === 'archive')
    return `https://archive.org/embed/${episode.videoId}?autoplay=1&start=${startOffset}`;
  return null;
}

// Export for use in index.html as globals
window.RETROTV = { CHANNELS, getCurrentBroadcast, getScheduleForChannel, getEmbedUrl };

package com.aj.giphysearch

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.aj.giphysearch.core.ui.GiphySearchTheme
import com.aj.giphysearch.navigation.MainScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            GiphySearchTheme {
                MainScreen()
            }
        }
    }
}

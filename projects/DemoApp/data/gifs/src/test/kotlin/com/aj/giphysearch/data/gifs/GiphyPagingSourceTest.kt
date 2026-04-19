package com.aj.giphysearch.data.gifs

import androidx.paging.PagingConfig
import androidx.paging.PagingSource
import androidx.paging.testing.TestPager
import com.aj.giphysearch.domain.gifs.model.Gif
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class GiphyPagingSourceTest {

    @Test
    fun `load first page successfully`() = runTest {
        val gifs = fakeGifList(25)
        val pagingSource = GiphyPagingSource { _, _ -> Result.success(gifs) }

        val pager = TestPager(PagingConfig(pageSize = 25), pagingSource)
        val result = pager.refresh() as PagingSource.LoadResult.Page

        assertEquals(25, result.data.size)
        assertNull(result.prevKey)
        assertNotNull(result.nextKey)
    }

    private fun fakeGifList(size: Int, startId: Int = 0): List<Gif> {
        return (0 until size).map {
            Gif(
                id = (startId + it).toString(),
                title = "Gif ${startId + it}",
                rating = "g",
                username = "user",
                source = "source",
                originalUrl = "url",
                previewUrl = "url",
                width = 100,
                height = 100
            )
        }
    }
}
